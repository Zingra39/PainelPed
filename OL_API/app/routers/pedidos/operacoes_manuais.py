"""Operações manuais sobre um pedido: retorno, espelho, reprocessamento,
observação, transmissão e cancelamento."""
import unicodedata
from datetime import datetime
from typing import Optional, cast

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Pedido
from app.schemas.pedido import ObservacaoBody, OperacaoResponse
from app.services import operacoes
from ol_core.core.exceptions import ErroConexaoBanco
from ol_core.core.logger import logger
from ol_core.layouts import formato_closeup
from ol_core.models.enums.tipo_status_erp import TipoStatusErp
from ol_core.models.enums.tipo_status_oper import TipoStatusOper

from ._comum import (
    _OPERACIONAL,
    _envio_somente_pronto,
    _get_pedido_para_operacao,
    _marcar_transmitindo,
)

router = APIRouter(prefix="/pedidos", tags=["Pedidos"])


def _bloquear_se_nao_pronto(pedido: Pedido, somente_pronto: bool) -> None:
    """422 se o envio está restrito a "Pronto" e o pedido está em outro status."""
    status = cast(Optional[str], pedido.status_operacional)
    if somente_pronto and status != TipoStatusOper.PRONTO.value:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Envio bloqueado pela parametrização: só pedidos com status 'Pronto' podem ser "
                f"transmitidos (status atual: '{status or '—'}'). Resolva as ocorrências e reprocesse o pedido."
            ),
        )


def _bloquear_se_em_analise(pedido: Pedido, acao: str) -> None:
    """422 se o pedido está em análise — transmitir/reprocessar só depois de
    encerrar a análise (que reprocessa o pedido)."""
    if cast(Optional[str], pedido.status_operacional) == TipoStatusOper.EM_ANALISE.value:
        quem = pedido.usuario_analise.nome if pedido.usuario_analise else None
        por = f" por {quem}" if quem else ""
        raise HTTPException(
            status_code=422,
            detail=f"Pedido em análise{por}. Encerre a análise antes de {acao}.",
        )


def _marcar_falha(pedido: Pedido, db: Session, motivo: str = TipoStatusOper.FALHA.value) -> None:
    """Marca o pedido como Falha quando uma ação manual encontra um erro inesperado.

    `motivo` permite identificar qual etapa falhou: os endpoints de retorno/espelho/
    cancelamento passam o "Falha no X" específico (mesmo valor que os services
    automáticos gravam), em vez do "Falha" genérico — assim dá pra saber qual
    operação falhou sem precisar olhar a tabela `arquivo`. Reprocessar/transmitir
    continuam usando o genérico (default), já que não têm coluna própria na tela
    de Rastreamento.

    Faz rollback antes: se o erro original veio do proprio SQLAlchemy (constraint,
    deadlock etc.), a sessao ja fica em estado de rollback pendente, e um commit()
    direto nela tende a estourar PendingRollbackError — um segundo erro que mascara
    o primeiro. Quem chama e responsavel por nao deixar essa falha (se houver)
    sobrescrever o HTTPException que ja estava sendo montado pro erro original.
    """
    db.rollback()
    setattr(pedido, "status_operacional", motivo)
    setattr(pedido, "atualizado_em", datetime.now())
    db.commit()


@router.post("/{id}/retorno", response_model=OperacaoResponse)
def gerar_retorno(id: int, db: Session = Depends(get_db), current_user=Depends(_OPERACIONAL),):
    pedido = _get_pedido_para_operacao(id, db)
    try:
        resultado = operacoes.executar_gerar_retorno(pedido, current_user.id)
        return OperacaoResponse(**resultado)
    except (ValueError, RuntimeError) as err_run:
        logger.exception(err_run)
        raise HTTPException(status_code=422, detail=str(err_run))
    except ErroConexaoBanco:
        raise
    except Exception as err:
        logger.exception(err)
        try:
            _marcar_falha(pedido, db, TipoStatusOper.FALHA_RETORNO.value)
        except ErroConexaoBanco:
            raise
        except Exception as err_marcar_falha:
            logger.error(f"Falha ao marcar pedido {id} como Falha após erro original: {err_marcar_falha}")
        raise HTTPException(status_code=500, detail="Erro ao gerar retorno")


@router.post("/{id}/espelho", response_model=OperacaoResponse)
def gerar_espelho(id: int, db: Session = Depends(get_db), current_user=Depends(_OPERACIONAL),):
    pedido = _get_pedido_para_operacao(id, db)
    try:
        resultado = operacoes.executar_gerar_espelho(pedido, current_user.id)
        return OperacaoResponse(**resultado)
    except (ValueError, RuntimeError) as err_run:
        logger.exception(err_run)
        raise HTTPException(status_code=422, detail=str(err_run))
    except ErroConexaoBanco:
        raise
    except Exception as err:
        logger.exception(err)
        try:
            _marcar_falha(pedido, db, TipoStatusOper.FALHA_ESPELHO.value)
        except ErroConexaoBanco:
            raise
        except Exception as err_marcar_falha:
            logger.error(f"Falha ao marcar pedido {id} como Falha após erro original: {err_marcar_falha}")
        raise HTTPException(status_code=500, detail="Erro ao gerar espelho")


@router.post("/{id}/reprocessar", response_model=OperacaoResponse)
def reprocessar(id: int, db: Session = Depends(get_db), current_user=Depends(_OPERACIONAL),):
    pedido = _get_pedido_para_operacao(id, db)
    _bloquear_se_em_analise(pedido, "reprocessar")
    try:
        resultado = operacoes.executar_reprocessar(pedido, current_user.id)
        return OperacaoResponse(**resultado)
    except (ValueError, RuntimeError) as err_run:
        logger.exception(err_run)
        raise HTTPException(status_code=422, detail=str(err_run))
    except ErroConexaoBanco:
        raise
    except Exception as err:
        logger.exception(err)
        try:
            _marcar_falha(pedido, db)
        except ErroConexaoBanco:
            raise
        except Exception as err_marcar_falha:
            logger.error(f"Falha ao marcar pedido {id} como Falha após erro original: {err_marcar_falha}")
        raise HTTPException(status_code=500, detail="Erro ao reprocessar")


# Campo "observação" do cabeçalho Close-Up (posições 87 a 186): o limite vem
# do formato do layout, o mesmo usado na leitura e na gravação do arquivo.
_TAMANHO_OBSERVACAO = formato_closeup.OBSERVACAO_TAMANHO


def _normalizar_observacao(texto: str) -> str:
    """Prepara o texto para um layout de largura fixa.

    Remove acentos (em UTF-8 um "ç" ocupa 2 bytes e desalinharia as colunas
    para quem lê o arquivo por byte) e colapsa quebras de linha/espaços
    repetidos, que quebrariam o registro de cabeçalho.
    """
    sem_acento = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode("ascii")
    return " ".join(sem_acento.split())


@router.patch("/{id}/observacao", response_model=OperacaoResponse)
def salvar_observacao(
    id: int,
    body: ObservacaoBody,
    db: Session = Depends(get_db),
    current_user=Depends(_OPERACIONAL),
):
    """Grava a observação da triagem no pedido.

    O texto é prefixado com o nome do usuário autenticado (ex.:
    "Larissa: PRAZO 30/60") — o nome vem do token, nunca do cliente, para a
    autoria não poder ser forjada. O conjunto precisa caber nos 100
    caracteres do campo do layout.

    Só vale para pedido ainda na triagem (status ERP "Não Transmitido"):
    depois de transmitido o arquivo já saiu, e editar aqui daria a falsa
    impressão de ter alterado o que foi enviado.
    """
    pedido = _get_pedido_para_operacao(id, db)

    if cast(Optional[str], pedido.status_erp) != TipoStatusErp.NAO_TRANSMITIDO.value:
        raise HTTPException(
            status_code=422,
            detail=(
                "A observação só pode ser alterada enquanto o pedido está na triagem "
                f"(status ERP atual: '{pedido.status_erp}')."
            ),
        )

    texto = _normalizar_observacao(body.observacao)
    autor = _normalizar_observacao(cast(Optional[str], current_user.nome) or "")

    if texto:
        composta = f"{autor}: {texto}" if autor else texto
        if len(composta) > _TAMANHO_OBSERVACAO:
            excedente = len(composta) - _TAMANHO_OBSERVACAO
            raise HTTPException(
                status_code=422,
                detail=(
                    f"A observação ficou com {len(composta)} caracteres (limite {_TAMANHO_OBSERVACAO}, "
                    f"já contando o prefixo '{autor}: '). Reduza {excedente} caractere(s)."
                ),
            )
    else:
        composta = ""

    try:
        setattr(pedido, "observacao", composta)
        setattr(pedido, "atualizado_em", datetime.now())
        db.commit()
    except ErroConexaoBanco:
        raise
    except Exception as err:
        logger.exception(err)
        db.rollback()
        raise HTTPException(status_code=500, detail="Erro ao salvar a observação")

    operacoes.registrar_log_observacao(
        cast(str, pedido.numero_pedido_ol), composta, current_user.id
    )

    return OperacaoResponse(
        sucesso=True,
        mensagem="Observação salva." if composta else "Observação removida.",
    )


@router.post("/{id}/transmitir", response_model=OperacaoResponse)
def transmitir(id: int, db: Session = Depends(get_db), current_user=Depends(_OPERACIONAL),):
    """Transmite (copia pra pasta_entrada da indústria) um único pedido —
    contraparte individual do /lote/transmitir, usada pelo botão de ação da
    linha e pela transmissão em lote dos itens selecionados na Confecção.

    Segue o mesmo contrato dos outros endpoints de operação manual (retorno,
    espelho, reprocessar, cancelamento): ValueError/RuntimeError = 422 sem
    marcar Falha, qualquer outra exceção = 500 e marca o pedido como Falha.
    """
    pedido = _get_pedido_para_operacao(id, db)
    if cast(Optional[str], pedido.status_erp) != TipoStatusErp.NAO_TRANSMITIDO.value:
        raise HTTPException(
            status_code=422,
            detail=f"Pedido já foi transmitido (status ERP atual: '{pedido.status_erp}').",
        )
    somente_pronto = _envio_somente_pronto(db)
    _bloquear_se_em_analise(pedido, "transmitir")
    _bloquear_se_nao_pronto(pedido, somente_pronto)
    # Fora do try de propósito: um HTTPException levantado aqui seria capturado
    # pelo `except Exception` abaixo e viraria 500 + pedido marcado como Falha.
    if not _marcar_transmitindo(pedido, db, somente_pronto=somente_pronto):
        # Outro operador marcou "Em Analise" (ou o pedido saiu de "Pronto") entre
        # a checagem acima e agora.
        _bloquear_se_em_analise(pedido, "transmitir")
        _bloquear_se_nao_pronto(pedido, somente_pronto)
        raise HTTPException(status_code=422, detail="Pedido em análise. Encerre a análise antes de transmitir.")
    try:
        resultado = operacoes.executar_transmitir(pedido, current_user.id)

        setattr(pedido, "status_erp", TipoStatusErp.TRANSMITIDO.value)
        setattr(pedido, "status_operacional", TipoStatusOper.TRANSMITIDO.value)
        setattr(pedido, "transmitido_em", datetime.now())
        setattr(pedido, "atualizado_em", datetime.now())
        db.commit()
        return OperacaoResponse(**resultado)
    except (ValueError, RuntimeError) as err_run:
        logger.exception(err_run)
        raise HTTPException(status_code=422, detail=str(err_run))
    except ErroConexaoBanco:
        raise
    except Exception as err:
        logger.exception(err)
        try:
            _marcar_falha(pedido, db)
        except ErroConexaoBanco:
            raise
        except Exception as err_marcar_falha:
            logger.error(f"Falha ao marcar pedido {id} como Falha após erro original: {err_marcar_falha}")
        raise HTTPException(status_code=500, detail="Erro ao transmitir")


@router.post("/{id}/cancelamento", response_model=OperacaoResponse)
def registrar_cancelamento(id: int, db: Session = Depends(get_db), current_user=Depends(_OPERACIONAL),):
    pedido = _get_pedido_para_operacao(id, db)
    try:
        resultado = operacoes.executar_cancelamento(pedido, current_user.id)
        return OperacaoResponse(**resultado)
    except (ValueError, RuntimeError) as err_run:
        logger.exception(err_run)
        raise HTTPException(status_code=422, detail=str(err_run))
    except ErroConexaoBanco:
        raise
    except Exception as err:
        logger.exception(err)
        try:
            _marcar_falha(pedido, db, TipoStatusOper.FALHA_CANCELAMENTO.value)
        except ErroConexaoBanco:
            raise
        except Exception as err_marcar_falha:
            logger.error(f"Falha ao marcar pedido {id} como Falha após erro original: {err_marcar_falha}")
        raise HTTPException(status_code=500, detail="Erro ao registrar cancelamento")
