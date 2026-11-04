"""Helpers compartilhados pelos módulos de rota de /pedidos: perfis de acesso,
filtros de listagem (busca, análise), contagem de ocorrências e as guardas de
transmissão usadas tanto pela operação individual quanto pela em lote."""
from datetime import datetime
from typing import Optional, cast

from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.core.deps import require_perfis
from app.models import Industria, Parametro, Pedido, PedidoOcorrencia
from ol_core.core.exceptions import ErroConexaoBanco
from ol_core.core.logger import logger
from ol_core.models.enums.tipo_severidade import TipoSeveridade
from ol_core.models.enums.tipo_status_oper import TipoStatusOper


_TODOS = require_perfis("Administrador", "Operador Logístico", "Gerente Comercial")


_OPERACIONAL = require_perfis("Administrador", "Operador Logístico")


def _conta_ocorrencias(db: Session, pedidos: list[Pedido]) -> tuple[dict[str, int], dict[str, int]]:
    try:
        # Contagem de ocorrências por pedido
        nums = [p.numero_pedido_ol for p in pedidos]
        total_oc = (
            db.query(PedidoOcorrencia.numero_pedido_ol, func.count().label("total"))
            .filter(PedidoOcorrencia.numero_pedido_ol.in_(nums))
            .group_by(PedidoOcorrencia.numero_pedido_ol)
            .all()
        ) if nums else []
        abertas_oc = (
            db.query(PedidoOcorrencia.numero_pedido_ol, func.count().label("total"))
            .filter(
                PedidoOcorrencia.numero_pedido_ol.in_(nums),
                PedidoOcorrencia.resolvido == False,  # noqa: E712
                _severidade_conta_como_pendencia(),
            )
            .group_by(PedidoOcorrencia.numero_pedido_ol)
            .all()
        ) if nums else []
        
        total_map = {r.numero_pedido_ol: r.total for r in total_oc}
        abertas_map = {r.numero_pedido_ol: r.total for r in abertas_oc}
        
        return total_map, abertas_map
    except ErroConexaoBanco as e:
        logger.error(f"Erro ao contar ocorrências: {e}")
        return {}, {}


def _fora_de_analise():
    """Filtro de query: exclui pedidos em análise. `!=` sozinho descartaria
    também as linhas com status NULL (NULL != x é NULL no SQL), por isso o or_."""
    return or_(
        Pedido.status_operacional.is_(None),
        Pedido.status_operacional != TipoStatusOper.EM_ANALISE.value,
    )


def _selo_analisado(p: Pedido) -> dict:
    """Selo "Analisado": quem concluiu a última análise e quando. Ao contrário
    de "Em Analise", persiste depois que a análise encerra (Pedido.analisado_por
    / analisado_em), então vale em qualquer status do pedido."""
    return {
        "analisado_por": p.usuario_analisou.nome if p.usuario_analisou else None,
        "analisado_em": cast(Optional[datetime], p.analisado_em),
    }


def _analise_campos(p: Pedido) -> dict:
    """Campos de análise para os schemas de resposta. Os de "Em Analise" só vêm
    preenchidos enquanto o pedido está nesse status (durante o encerramento, com
    o status já em Reprocessando, o "em análise" some); os do selo "Analisado"
    (`_selo_analisado`) vêm sempre que o pedido já foi analisado."""
    if cast(Optional[str], p.status_operacional) != TipoStatusOper.EM_ANALISE.value:
        return {"id_usuario_analise": None, "em_analise_por": None, "em_analise_desde": None, **_selo_analisado(p)}
    return {
        "id_usuario_analise": cast(Optional[int], p.id_usuario_analise),
        "em_analise_por": p.usuario_analise.nome if p.usuario_analise else None,
        "em_analise_desde": cast(Optional[datetime], p.em_analise_desde),
        **_selo_analisado(p),
    }


def _severidade_conta_como_pendencia():
    """Critério de SQL: a ocorrência com severidade "IGNORADO" (parâmetro de
    ignorar ligado — ver TipoSeveridade.IGNORADO e a tela de Parametrização) não
    é pendência, então não entra no contador de ocorrências da Triagem nem da
    planilha dela. Severidade NULL (ocorrência sem classificação) continua
    contando: em SQL `severidade != 'IGNORADO'` sozinho descartaria os NULL."""
    return or_(
        PedidoOcorrencia.severidade.is_(None),
        PedidoOcorrencia.severidade != TipoSeveridade.IGNORADO.value,
    )


def _filtrar_busca(q, busca: Optional[str]):
    """Campo único de pesquisa das listagens (Triagem, Rastreamento, Histórico).

    O texto é quebrado em palavras-chave e CADA palavra precisa aparecer em ao
    menos um dos campos: número do pedido, CNPJ, nome do arquivo ou indústria —
    "43410436 ACME" acha os pedidos daquele cliente na indústria ACME. Para o
    CNPJ a palavra também é comparada só pelos dígitos, então colar
    "43.410.436/0001-61" (formatado) acha o "43410436000161" gravado."""
    if not busca:
        return q
    for termo in busca.split():
        padrao = f"%{termo}%"
        condicoes = [
            Pedido.numero_pedido_ol.ilike(padrao),
            Pedido.cnpj_cliente.ilike(padrao),
            Pedido.nome_arquivo.ilike(padrao),
            Pedido.industria.has(Industria.nome.ilike(padrao)),
        ]
        digitos = "".join(c for c in termo if c.isdigit())
        if digitos and digitos != termo:
            condicoes.append(Pedido.cnpj_cliente.ilike(f"%{digitos}%"))
        q = q.filter(or_(*condicoes))
    return q


def _filtrar_analisado(q, analisado: Optional[bool]):
    """Filtro do selo "Analisado": True = já analisados, False = nunca analisados,
    None = sem filtro. Usado na listagem e no export da Triagem, para a planilha
    bater com a tela."""
    if analisado is True:
        return q.filter(Pedido.analisado_em.isnot(None))
    if analisado is False:
        return q.filter(Pedido.analisado_em.is_(None))
    return q



def _get_pedido_para_operacao(id: int, db: Session) -> Pedido:
    pedido = (
        db.query(Pedido)
        .options(joinedload(Pedido.industria), joinedload(Pedido.usuario_analise))
        .filter(Pedido.id == id)
        .first()
    )
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido não encontrado.")
    return pedido


# Parâmetro (tela de Parametrização): com ele LIGADO ("1"), a transmissão manual
# — individual e em lote — só aceita pedidos com status_operacional "Pronto".
# Pedido em "Verificar" (ou qualquer outro status) fica barrado até a ocorrência
# ser resolvida e o pedido reprocessado. Não afeta a transmissão automática, que
# já só age em pedidos "Pronto". Ausente ou desligado = comportamento antigo.
_CHAVE_ENVIO_SOMENTE_PRONTO = "BLOQUEAR_ENVIO_PEDIDO_VERIFICAR"


def _envio_somente_pronto(db: Session) -> bool:
    """True se o envio manual está restrito a pedidos "Pronto". Qualquer falha
    de leitura vira False (fail-safe igual a `parametro_esta_ativo`: erro de
    banco nunca pode virar bloqueio por acidente nem derrubar a tela)."""
    try:
        p = db.query(Parametro).filter(Parametro.chave == _CHAVE_ENVIO_SOMENTE_PRONTO).first()
        return p is not None and (p.valor or "").strip() == "1"
    except ErroConexaoBanco:
        raise
    except Exception as err:
        logger.error(f"[_envio_somente_pronto] {err}")
        return False


def _marcar_transmitindo(p: Pedido, db: Session, somente_pronto: bool = False) -> bool:
    """Marca o pedido como "Transmitindo" SE ele não estiver em análise (e, com
    `somente_pronto`, SE estiver "Pronto") — numa única instrução UPDATE condicional.

    O check-then-set (ler o status, depois gravar) deixaria uma janela em que
    outro operador marca "Em Analise" entre a leitura e a gravação, e o pedido
    seria transmitido do mesmo jeito; no lote essa janela dura o tempo do loop
    inteiro. O WHERE faz a checagem e a troca de status serem atômicas.

    Devolve False (sem alterar nada) se o pedido está em análise ou, com
    `somente_pronto`, se deixou de estar "Pronto" (ex.: voltou para "Verificar"
    depois de a lista do lote ser montada)."""
    q = db.query(Pedido).filter(Pedido.id == p.id, _fora_de_analise())
    if somente_pronto:
        q = q.filter(Pedido.status_operacional == TipoStatusOper.PRONTO.value)
    linhas = (
        q
        .update(
            {
                Pedido.status_operacional: TipoStatusOper.TRANSMITINDO.value,
                Pedido.atualizado_em: datetime.now(),
            },
            synchronize_session=False,
        )
    )
    db.commit()
    db.refresh(p)
    return bool(linhas)
