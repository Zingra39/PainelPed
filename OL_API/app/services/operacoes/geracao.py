"""Geração manual de arquivos a partir do ERP: retorno, espelho e cancelamento.

Junto ficam as regras de status que só elas usam: quais status permitem gerar,
a trava "Sendo Gerado" (reserva atômica no banco) e a devolução do status
anterior quando a geração falha."""
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable

from ol_core.core.exceptions import ErroConexaoBanco
from ol_core.core.logger import logger
from ol_core.database.mysql.contexto_parametros import exigir_cnpj_distribuidor
from ol_core.database.mysql.contexto_pedidos import atualizar_status_pedido, reservar_status_pedido
from ol_core.database.sqlserver.contexto_pedido import verifica_pedido
from ol_core.database.sqlserver.contexto_titulo import verificar_titulo
from ol_core.models.enums.tipo_arquivo import TipoArquivo
from ol_core.models.enums.tipo_status_erp import TipoStatusErp
from ol_core.models.enums.tipo_status_oper import TipoStatusOper
from ol_core.models import regras_status
from ol_core.layouts import LayoutIntegracao, LayoutNaoSuportado, Operacao, layout_de, layout_por_tipo

from .conversao import _build_industria, _build_pedido, _layout
from .historico import _log
from .titulo_erp import _sem_nulo




def _restaurar_status(numero_pedido_ol, status_anterior) -> None:
    """Devolve o pedido ao status de antes de uma geração que falhou — inclusive
    quando a falha foi ErroConexaoBanco do ERP (o MySQL segue de pé e o pedido
    não pode ficar preso em "X Sendo Gerado", que bloqueia novas tentativas).
    Se quem caiu foi o próprio MySQL, não há como restaurar: só registra; o
    erro original continua subindo em quem chamou."""
    if not numero_pedido_ol:
        return
    try:
        atualizar_status_pedido(numero_pedido_ol, status_anterior)
    except ErroConexaoBanco as erro:
        logger.error(
            f"Não foi possível restaurar o status do pedido {numero_pedido_ol} para "
            f"'{status_anterior}': {erro.detail}"
        )


# Regra do retorno manual por atraso: se o pedido foi transmitido e o retorno
# não foi gerado em até este prazo, a geração manual é liberada. Fixo no código
# por enquanto (pode virar parâmetro depois).
LIMITE_RETORNO_MANUAL = timedelta(hours=1)


def retorno_manual_liberado_por_atraso(pedido_db, agora: "datetime | None" = None) -> bool:
    """True se o pedido está transmitido, sem retorno gerado, há 1h ou mais.

    Fonte única da regra: usada pelo gate de `executar_gerar_retorno` e pelos
    schemas (campo `retorno_manual_liberado`) que alimentam a tela, para
    backend e frontend nunca divergirem. Sem `transmitido_em` não libera.
    """
    if pedido_db.status_erp != TipoStatusErp.TRANSMITIDO.value:
        return False
    if pedido_db.status_operacional not in regras_status.AGUARDANDO_RETORNO:
        return False
    transmitido_em = getattr(pedido_db, "transmitido_em", None)
    if transmitido_em is None:
        return False
    if any(
        (a.tipo or "").lower() == TipoArquivo.RETORNO.value and a.situacao == TipoStatusOper.RETORNO.value
        for a in (pedido_db.arquivos or [])
    ):
        return False
    return (agora or datetime.now()) - transmitido_em >= LIMITE_RETORNO_MANUAL


def acoes_de_geracao_manual(pedido_db) -> dict[str, bool]:
    """Quais gerações manuais a tela deve oferecer para o pedido — campos
    `pode_gerar_*` dos schemas. A tela não tem regra própria: só lê estes
    campos, e eles usam as mesmas regras que os `executar_*` aplicam (status em
    regras_status, layout da indústria gerar o arquivo e, no cancelamento,
    pedido não faturado). Assim o botão só aparece quando a geração é aceita."""
    status = pedido_db.status_operacional
    return {
        "pode_gerar_retorno": (
            (status in regras_status.PODE_GERAR_RETORNO_MANUAL or retorno_manual_liberado_por_atraso(pedido_db))
            and _industria_gera(pedido_db, Operacao.RETORNO)
        ),
        "pode_gerar_espelho": (
            status in regras_status.PODE_GERAR_ESPELHO_MANUAL
            and _industria_gera(pedido_db, Operacao.ESPELHO)
        ),
        "pode_gerar_cancelamento": (
            status in regras_status.PODE_GERAR_CANCELAMENTO_MANUAL
            and not _erp_bloqueia_cancelamento(pedido_db)
            and _industria_gera(pedido_db, Operacao.CANCELAMENTO)
        ),
    }


def _industria_gera(pedido_db, operacao: Operacao) -> bool:
    """O layout configurado na indústria do pedido está implementado e gera o arquivo?"""
    industria_db = pedido_db.industria
    if not industria_db:
        return False
    try:
        layout = layout_por_tipo(_layout(industria_db.layout))
    except (ValueError, LayoutNaoSuportado):
        return False
    return layout.suporta(operacao)


def _reservar_geracao(pedido_db, status_gerando: str, status_antes) -> None:
    """Marca o pedido como "<X> Sendo Gerado" SE o status ainda for o que o
    gate acabou de validar — compare-and-set atômico no banco, como a
    transmissão (_marcar_transmitindo). Se o serviço automático (ou outro
    operador) mudou o status nesse meio-tempo, nada é gravado e a geração
    manual não começa."""
    numero = pedido_db.numero_pedido_ol
    if numero and not reservar_status_pedido(numero, status_gerando, status_esperado=status_antes):
        raise ValueError(
            f"O status do pedido {numero} mudou enquanto a geração era iniciada "
            "(possivelmente o serviço automático começou a processá-lo). "
            "Atualize a tela e tente novamente."
        )


def _bloquear_se_em_geracao(pedido_db) -> None:
    """Checagem rápida, só para a mensagem: a garantia contra geração em dobro
    é o UPDATE condicional de `_reservar_geracao`."""
    status = pedido_db.status_operacional
    if status in regras_status.EM_GERACAO:
        raise ValueError(
            f"O pedido {pedido_db.numero_pedido_ol} está com '{status}'. "
            "Aguarde a conclusão antes de gerar manualmente."
        )


# ------------------------------------------------------------------ fluxo comum


@dataclass(frozen=True)
class _TipoGeracao:
    """O que muda entre retorno, espelho e cancelamento no fluxo comum."""

    nome: str  # usado nas mensagens: "Falha ao gerar <nome> para o pedido ..."
    status_gerando: str
    acao_historico: str
    detalhe_historico: str  # formatado com {id_usuario}
    mensagem_sucesso: str  # formatado com {numero}


_RETORNO = _TipoGeracao(
    nome="retorno",
    status_gerando=TipoStatusOper.GERANDO_RETORNO.value,
    acao_historico="Retorno gerado manualmente",
    detalhe_historico="Arquivo de retorno gerado via painel pelo usuário {id_usuario}.",
    mensagem_sucesso="Retorno gerado para pedido {numero}.",
)
_ESPELHO = _TipoGeracao(
    nome="espelho",
    status_gerando=TipoStatusOper.GERANDO_ESPELHO.value,
    acao_historico="Espelho gerado manualmente",
    detalhe_historico="Arquivo espelho gerado via painel pelo usuário {id_usuario}.",
    mensagem_sucesso="Espelho gerado para pedido {numero}.",
)
_CANCELAMENTO = _TipoGeracao(
    nome="cancelamento",
    status_gerando=TipoStatusOper.GERANDO_CANCELAMENTO.value,
    acao_historico="Cancelamento gerado manualmente",
    detalhe_historico="Arquivo de cancelamento gerado via painel pelo usuário {id_usuario}.",
    mensagem_sucesso="Cancelamento gerado para pedido {numero}.",
)


def _gerar_com_trava(
    pedido_db,
    id_usuario: int,
    tipo: _TipoGeracao,
    *,
    status_antes,
    status_final: str,
    gerar: Callable[[object], bool],
) -> dict:
    """Esqueleto das gerações manuais, chamado DEPOIS do gate de status de cada uma.

    1. exige o CNPJ do distribuidor (sem ele: 422 com o motivo, antes de reservar);
    2. reserva o pedido em "<X> Sendo Gerado" (compare-and-set no banco);
    3. roda `gerar(pedido_db)`; se ela levantar ou devolver False, volta o pedido
       ao status de antes — não necessariamente "<X> Gerado" — em vez de deixá-lo
       preso em "Sendo Gerado". Vale também para ErroConexaoBanco: se quem caiu
       foi o ERP, o MySQL está de pé e o status precisa voltar;
    4. em caso de sucesso grava `status_final` e registra no histórico.
    """
    numero_pedido_ol = pedido_db.numero_pedido_ol
    exigir_cnpj_distribuidor()
    _reservar_geracao(pedido_db, tipo.status_gerando, status_antes)

    try:
        if not gerar(pedido_db):
            raise RuntimeError(
                f"Falha ao gerar {tipo.nome} para o pedido {numero_pedido_ol}. Verifique os logs."
            )
    except Exception:
        _restaurar_status(numero_pedido_ol, status_antes)
        raise

    if numero_pedido_ol:
        atualizar_status_pedido(numero_pedido_ol, status_final)

    _log(
        numero_pedido_ol,
        tipo.acao_historico,
        tipo.detalhe_historico.format(id_usuario=id_usuario),
        id_usuario,
    )
    return {"sucesso": True, "mensagem": tipo.mensagem_sucesso.format(numero=numero_pedido_ol)}


def _layout_que_gera(industria_ol, operacao: Operacao) -> LayoutIntegracao:
    """Layout registrado da indústria, se ele gerar o arquivo pedido. Chamado
    dentro da geração (depois da reserva): o ValueError faz o fluxo comum
    devolver o pedido ao status de antes, com a mensagem para a tela."""
    try:
        layout = layout_de(industria_ol)
    except LayoutNaoSuportado as erro:
        raise ValueError(f"{erro}. Não é possível gerar {operacao.value} para esta indústria.") from None
    if not layout.suporta(operacao):
        raise ValueError(f"O layout {layout.tipo.value} da indústria não gera {operacao.value}.")
    return layout


def _industria_do_pedido(pedido_db):
    industria_db = pedido_db.industria
    if not industria_db:
        raise ValueError("Indústria do pedido não encontrada.")
    return industria_db


def _pedido_no_erp(pedido_db, tipo: _TipoGeracao):
    """Primeiro registro do pedido no ERP; sem ele não há o que gerar."""
    pedidos_erp = verifica_pedido(pedido_db.numero_pedido_ol)
    if not pedidos_erp:
        raise ValueError(
            f"Pedido {pedido_db.numero_pedido_ol} ainda não localizado no ERP. "
            f"Não é possível gerar o {tipo.nome} no momento."
        )
    return pedidos_erp[0]


# ------------------------------------------------------------------ retorno


def executar_gerar_retorno(pedido_db, id_usuario: int) -> dict:
    # Geração manual só é permitida depois que o service já gerou o retorno
    # automaticamente — inclusive se o pedido já avançou pra Espelho ou
    # Cancelamento (regerar o retorno é válido nesses estágios também, e não
    # deve fazer o pedido "regredir" pra trás na esteira — por isso o status
    # anterior é preservado abaixo, em vez de travado em "Retorno Gerado").
    _bloquear_se_em_geracao(pedido_db)
    status_antes = pedido_db.status_operacional
    if (
        status_antes not in regras_status.PODE_GERAR_RETORNO_MANUAL
        and not retorno_manual_liberado_por_atraso(pedido_db)
    ):
        raise ValueError(
            f"Geração manual de retorno só é permitida após o serviço automático gerá-lo, "
            f"se ele falhar ou se o retorno não for gerado até 1h após a transmissão "
            f"(status atual do pedido: '{pedido_db.status_operacional}')."
        )

    # Regerar um retorno já existente (pedido em Retorno/Espelho/Cancelamento
    # Gerado) preserva o status anterior, pra não fazer o pedido "regredir".
    # Se o retorno ainda não existia (veio de falha ou de atraso pós-
    # transmissão), o sucesso leva o pedido para "Retorno Gerado".
    status_final = (
        status_antes
        if status_antes in regras_status.RETORNO_REGERADO_MANTEM_STATUS
        else TipoStatusOper.RETORNO.value
    )
    return _gerar_com_trava(
        pedido_db, id_usuario, _RETORNO,
        status_antes=status_antes, status_final=status_final, gerar=_gerar_retorno,
    )


def _gerar_retorno(pedido_db) -> bool:
    industria_ol = _build_industria(_industria_do_pedido(pedido_db))
    pedido_ol = _build_pedido(pedido_db)

    pedido_erp = _pedido_no_erp(pedido_db, _RETORNO)
    pedido_ol.codigo_interno_pedido = pedido_erp.codigo_interno_pedido
    pedido_ol.cod_situacao = pedido_erp.cod_situacao
    pedido_ol.situacao = pedido_erp.situacao
    pedido_ol.data_cancelamento = pedido_erp.data_cancelamento
    pedido_ol.quem_cancelou = pedido_erp.quem_cancelou
    pedido_ol.data_faturamento = pedido_erp.data_faturamento

    return _layout_que_gera(industria_ol, Operacao.RETORNO).gerar_retorno(industria_ol, pedido_ol)


# ------------------------------------------------------------------ espelho


def executar_gerar_espelho(pedido_db, id_usuario: int) -> dict:
    # Geração manual só é permitida depois que o service já gerou o espelho
    # automaticamente (status "Espelho Gerado") — evita conflito entre geração
    # manual e automática (Issue #40). Também permitido quando o espelho
    # falhou: nova tentativa só manual.
    _bloquear_se_em_geracao(pedido_db)
    status_antes = pedido_db.status_operacional
    if status_antes not in regras_status.PODE_GERAR_ESPELHO_MANUAL:
        raise ValueError(
            f"Geração manual de espelho só é permitida após o serviço automático gerá-lo "
            f"ou quando o espelho falhou (status atual do pedido: '{pedido_db.status_operacional}')."
        )

    return _gerar_com_trava(
        pedido_db, id_usuario, _ESPELHO,
        status_antes=status_antes, status_final=TipoStatusOper.ESPELHO.value, gerar=_gerar_espelho,
    )


def _gerar_espelho(pedido_db) -> bool:
    if not pedido_db.nome_arquivo:
        raise ValueError("Pedido não possui nome de arquivo registrado.")
    industria_db = _industria_do_pedido(pedido_db)

    nome_arquivo_base = os.path.basename(pedido_db.nome_arquivo)
    titulo_ol = next(
        (
            t for t in (verificar_titulo(nome_arquivo_base) or [])
            if t.nome_arquivo and nome_arquivo_base in os.path.basename(str(t.nome_arquivo))
        ),
        None,
    )
    if not titulo_ol:
        raise ValueError(
            "Nenhum título (NF) encontrado no ERP para este pedido. "
            "O espelho exige que a NF já esteja emitida."
        )
    if not _sem_nulo(getattr(titulo_ol, "data_emissao", None)):
        raise ValueError(
            f"Pedido {pedido_db.numero_pedido_ol} ainda não possui data de emissão da NF no ERP. "
            "O espelho exige que a NF já esteja emitida."
        )

    industria_ol = _build_industria(industria_db)
    return _layout_que_gera(industria_ol, Operacao.ESPELHO).gerar_espelho(industria_ol, titulo_ol)


# ------------------------------------------------------------------ cancelamento


def executar_cancelamento(pedido_db, id_usuario: int) -> dict:
    # Geração manual só é permitida depois que o service já gerou o cancelamento
    # automaticamente (status "Cancelamento Gerado") — evita conflito entre
    # geração manual e automática (Issue #40). Também permitido quando o
    # cancelamento falhou: nova tentativa só manual.
    _bloquear_se_em_geracao(pedido_db)
    status_antes = pedido_db.status_operacional
    if status_antes not in regras_status.PODE_GERAR_CANCELAMENTO_MANUAL:
        raise ValueError(
            f"Geração manual de cancelamento só é permitida após o serviço automático gerá-lo "
            f"ou quando o cancelamento falhou (status atual do pedido: '{pedido_db.status_operacional}')."
        )

    return _gerar_com_trava(
        pedido_db, id_usuario, _CANCELAMENTO,
        status_antes=status_antes, status_final=TipoStatusOper.CANCELADO.value, gerar=_gerar_cancelamento,
    )


def _erp_bloqueia_cancelamento(pedido_db) -> bool:
    """Pedido já faturado (Espelho gerado) não é cancelado pelo painel: o
    cancelamento da NF é feito direto no ERP. Qualquer outro estágio é aceito —
    inclusive "Pedido Cancelado", que é onde o pedido fica depois de um
    cancelamento gerado, para permitir regerar o arquivo."""
    status_erp = (pedido_db.status_erp or "").strip().lower()
    return status_erp in {s.lower() for s in regras_status.ERP_CANCELAMENTO_MANUAL_BLOQUEADO}


def _gerar_cancelamento(pedido_db) -> bool:
    # O ERP ainda precisa confirmar o cancelamento (data_cancelamento, abaixo).
    if _erp_bloqueia_cancelamento(pedido_db):
        raise ValueError(
            f"Status atual '{pedido_db.status_erp}' não permite cancelamento via painel. "
            "Realize o cancelamento diretamente no ERP."
        )

    industria_db = _industria_do_pedido(pedido_db)
    industria_ol = _build_industria(industria_db)
    if industria_ol.pasta_envio_cancelamento is None:
        raise ValueError(
            f"Campo 'pasta_envio_cancelamento' não configurado para a indústria '{industria_db.nome}'. "
            "Configure o campo antes de gerar cancelamentos."
        )
    pedido_ol = _build_pedido(pedido_db)

    pedido_erp = _pedido_no_erp(pedido_db, _CANCELAMENTO)
    if not pedido_erp.data_cancelamento:
        raise ValueError(
            f"Pedido {pedido_db.numero_pedido_ol} não consta como cancelado no ERP. "
            "O cancelamento deve ser realizado no ERP antes de gerar o arquivo pelo painel."
        )
    pedido_ol.codigo_interno_pedido = pedido_erp.codigo_interno_pedido
    pedido_ol.cod_situacao = pedido_erp.cod_situacao
    pedido_ol.data_cancelamento = pedido_erp.data_cancelamento
    pedido_ol.quem_cancelou = pedido_erp.quem_cancelou

    return _layout_que_gera(industria_ol, Operacao.CANCELAMENTO).gerar_cancelamento(industria_ol, pedido_ol)
