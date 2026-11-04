"""Entrada e saída do status "Em Analise"."""
from datetime import datetime
from typing import Optional, cast

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import _perfil_equivalente
from app.models import Pedido
from app.schemas.pedido import OperacaoResponse
from app.services import operacoes
from ol_core.core.exceptions import ErroConexaoBanco
from ol_core.core.logger import logger
from ol_core.models.enums.tipo_status_erp import TipoStatusErp
from ol_core.models.enums.tipo_status_oper import TipoStatusOper
from ol_core.models import regras_status

from ._comum import _OPERACIONAL, _get_pedido_para_operacao

router = APIRouter(prefix="/pedidos", tags=["Pedidos"])


# Um operador marca o pedido como "Em Analise" na triagem para os demais saberem
# que ele está sendo cuidado e ninguém o transmitir por acidente. Enquanto
# estiver nesse status o pedido fica fora de toda transmissão e de todo
# reprocessamento (individual e em lote) — a única saída é encerrar a análise,
# o que reprocessa o pedido e o devolve como Pronto ou Verificar.
# De onde pode entrar e o que é um encerramento válido: regras_status
# (PODE_ENTRAR_EM_ANALISE / RESULTADO_VALIDO_POS_ANALISE).


@router.post("/{id}/analise", response_model=OperacaoResponse)
def iniciar_analise(id: int, db: Session = Depends(get_db), current_user=Depends(_OPERACIONAL),):
    """Marca o pedido como "Em Analise" por quem chamou.

    Só pedido ainda na triagem (status ERP "Não Transmitido") e em Pronto ou
    Verificar entra em análise. A marcação é um UPDATE condicional (o próprio
    WHERE confere o status): se dois operadores clicam ao mesmo tempo, só um
    UPDATE casa a linha e o outro recebe 409 informando quem chegou primeiro.
    """
    pedido = _get_pedido_para_operacao(id, db)
    if cast(Optional[str], pedido.status_erp) != TipoStatusErp.NAO_TRANSMITIDO.value:
        raise HTTPException(
            status_code=422,
            detail=(
                "Só é possível analisar um pedido que ainda está na triagem "
                f"(status ERP atual: '{pedido.status_erp}')."
            ),
        )

    agora = datetime.now()
    try:
        linhas = (
            db.query(Pedido)
            .filter(
                Pedido.id == pedido.id,
                Pedido.status_erp == TipoStatusErp.NAO_TRANSMITIDO.value,
                Pedido.status_operacional.in_(regras_status.PODE_ENTRAR_EM_ANALISE),
            )
            .update(
                {
                    Pedido.status_operacional: TipoStatusOper.EM_ANALISE.value,
                    Pedido.id_usuario_analise: current_user.id,
                    Pedido.em_analise_desde: agora,
                    Pedido.atualizado_em: agora,
                },
                synchronize_session=False,
            )
        )
        db.commit()
    except ErroConexaoBanco:
        raise
    except Exception as err:
        logger.exception(err)
        db.rollback()
        raise HTTPException(status_code=500, detail="Erro ao marcar o pedido como em análise.")

    if not linhas:
        # Perdeu a corrida (ou o status não permite): relê para dizer o porquê.
        db.refresh(pedido)
        if cast(Optional[str], pedido.status_operacional) == TipoStatusOper.EM_ANALISE.value:
            quem = pedido.usuario_analise.nome if pedido.usuario_analise else None
            por = f" por {quem}" if quem else ""
            raise HTTPException(status_code=409, detail=f"Este pedido já está em análise{por}.")
        raise HTTPException(
            status_code=422,
            detail=(
                f"O pedido não pode entrar em análise no status atual ('{pedido.status_operacional}'). "
                "Só pedidos Pronto ou Verificar."
            ),
        )

    operacoes.registrar_log_analise(
        cast(str, pedido.numero_pedido_ol),
        "Análise iniciada",
        f"Pedido marcado como em análise por {current_user.nome}.",
        current_user.id,
    )
    return OperacaoResponse(sucesso=True, mensagem="Pedido marcado como em análise.")


@router.delete("/{id}/analise", response_model=OperacaoResponse)
def encerrar_analise(id: int, db: Session = Depends(get_db), current_user=Depends(_OPERACIONAL),):
    """Encerra a análise: reprocessa o pedido e o devolve como Pronto ou Verificar.

    Quem encerra: o próprio autor da análise ou um Administrador (para destravar
    um pedido deixado em análise por quem saiu sem encerrar).

    O reprocessamento é o mesmo do botão "Reprocessar" — revalida o pedido e
    grava Pronto (sem pendências) ou Verificar (com ocorrências). Se ele falhar
    por qualquer motivo, a análise NÃO é encerrada: o pedido volta para
    "Em Analise", com o mesmo autor, e o erro é devolvido ao operador para
    tentar de novo. Nunca deixa o pedido preso em "Reprocessando".
    """
    pedido = _get_pedido_para_operacao(id, db)
    if cast(Optional[str], pedido.status_operacional) != TipoStatusOper.EM_ANALISE.value:
        raise HTTPException(status_code=422, detail="Este pedido não está em análise.")

    perfil_nome = current_user.perfil.nome if current_user.perfil else None
    eh_admin = _perfil_equivalente(perfil_nome, "Administrador")
    if cast(Optional[int], pedido.id_usuario_analise) != current_user.id and not eh_admin:
        quem = pedido.usuario_analise.nome if pedido.usuario_analise else "outro usuário"
        raise HTTPException(
            status_code=403,
            detail=f"Somente {quem} ou um Administrador pode encerrar esta análise.",
        )

    id_pedido = cast(int, pedido.id)
    numero = cast(str, pedido.numero_pedido_ol)

    # Reivindica o encerramento de forma atômica (Em Analise -> Reprocessando):
    # dois cliques/pessoas encerrando juntos não reprocessam duas vezes.
    linhas = (
        db.query(Pedido)
        .filter(Pedido.id == id_pedido, Pedido.status_operacional == TipoStatusOper.EM_ANALISE.value)
        .update(
            {Pedido.status_operacional: TipoStatusOper.REPROCESSANDO.value, Pedido.atualizado_em: datetime.now()},
            synchronize_session=False,
        )
    )
    db.commit()
    if not linhas:
        raise HTTPException(status_code=409, detail="A análise deste pedido já foi encerrada.")

    mensagem_reproc = ""
    erro: Optional[str] = None
    status_http = 422
    try:
        db.refresh(pedido)
        resultado = operacoes.executar_reprocessar(pedido, current_user.id)
        mensagem_reproc = str(resultado.get("mensagem", ""))
    except (ValueError, RuntimeError) as err_run:
        logger.exception(err_run)
        erro = str(err_run)
    except ErroConexaoBanco:
        raise
    except Exception as err:
        logger.exception(err)
        erro = "Erro ao reprocessar o pedido."
        status_http = 500

    # O reprocessamento grava o status por uma conexão própria (ol_core). Encerrar
    # a transação aberta antes de reler: com REPEATABLE READ a sessão continuaria
    # enxergando o status de antes dele.
    db.rollback()
    db.refresh(pedido)
    status_final = cast(Optional[str], pedido.status_operacional)

    if erro is None and status_final in regras_status.RESULTADO_VALIDO_POS_ANALISE:
        db.query(Pedido).filter(Pedido.id == id_pedido).update(
            {
                Pedido.id_usuario_analise: None,
                Pedido.em_analise_desde: None,
                # Selo "Analisado": só aqui, com a análise concluída com sucesso.
                Pedido.analisado_por: current_user.id,
                Pedido.analisado_em: datetime.now(),
                Pedido.atualizado_em: datetime.now(),
            },
            synchronize_session=False,
        )
        db.commit()
        operacoes.registrar_log_analise(
            numero,
            "Análise encerrada",
            f"Análise encerrada por {current_user.nome}. Pedido reprocessado e marcado como '{status_final}'.",
            current_user.id,
        )
        return OperacaoResponse(
            sucesso=True,
            mensagem=f"Análise encerrada. O pedido voltou para '{status_final}'. {mensagem_reproc}".strip(),
        )

    # Falhou: o pedido volta para "Em Analise" (autor e data preservados) — nunca
    # fica preso em "Reprocessando".
    db.query(Pedido).filter(Pedido.id == id_pedido).update(
        {Pedido.status_operacional: TipoStatusOper.EM_ANALISE.value, Pedido.atualizado_em: datetime.now()},
        synchronize_session=False,
    )
    db.commit()
    operacoes.registrar_log_analise(
        numero,
        "Falha ao encerrar análise",
        f"Não foi possível reprocessar o pedido ao encerrar a análise: {erro or mensagem_reproc}. Pedido segue em análise.",
        current_user.id,
    )
    raise HTTPException(
        status_code=status_http,
        detail=f"Não foi possível encerrar a análise: {erro or mensagem_reproc} O pedido continua em análise.",
    )
