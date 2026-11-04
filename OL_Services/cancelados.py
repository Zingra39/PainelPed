from datetime import datetime, timedelta
from ol_core.core.logger import logger
from ol_core.models.enums.tipo_status_oper import TipoStatusOper
from ol_core.services.import_service import LayouFactory
from ol_core.layouts import Operacao, industria_suporta
from ol_core.core.variaveis_globais import industrias_ativas
from ol_core.database.mysql.contexto_parametros import exigir_cnpj_distribuidor
from ol_core.core.config import inicializar_processo, pasta_da_aplicacao
from ol_core.database.mysql.contexto_servico import atualizar_status_servico
from ol_core.database.mysql.contexto_arquivo import verificar_cancelado_existente
from ol_core.database.sqlserver.contexto_cancelamento import verifica_arquivos_cancelados
from ol_core.database.mysql.contexto_pedidos import atualizar_dados_pedido, atualizar_status_pedido, reservar_status_pedido, verifica_dados_pedido, verifica_pedido_existente


_SERVICO = "cancelados"


def atualizar_status_para_aguardando(pedidos: list) -> list:
    pedido_com_numero_ol = []
    for pedido in pedidos:
        if pedido.numero_pedido_ol is None:
            logger.error(f"Pedido {pedido.nome_arquivo} não possui número de pedido ol")
            continue

        id_arquivo = verificar_cancelado_existente(pedido.numero_pedido_ol)
        if id_arquivo is not None:
            logger.warning("Arquivo de Cancelado já foi gerado")
            continue

        else:
            # Não sobrescreve um pedido em geração (ex.: geração manual pelo
            # painel em andamento) — UPDATE condicional atômico.
            if reservar_status_pedido(pedido.numero_pedido_ol, TipoStatusOper.AGUARDANDO_CANCELAMENTO.value):
                pedido_com_numero_ol.append(pedido)
            else:
                logger.warning(f"Pedido {pedido.numero_pedido_ol} já está em geração — pulando.")
    return pedido_com_numero_ol


def processar_industria(industria) -> None:
    # Layout sem cancelamento: nenhum pedido é tocado.
    if not industria_suporta(industria, Operacao.CANCELAMENTO):
        return

    data_atual = datetime.now() - timedelta(days=30)
    pedidos = verifica_arquivos_cancelados(industria.id_bbs, data_atual.strftime("%Y-%m-%d"))

    if pedidos:
        pedidos = atualizar_status_para_aguardando(pedidos)

    if pedidos is None:
        logger.warning("Nenhum pedido foi encontrado para gerar cancelamento")
        return

    for pedido in pedidos:
        if pedido.numero_pedido_ol is None:
            logger.error(f"Pedido {pedido.nome_arquivo} não possui número de pedido ol")
            continue

        if not verifica_pedido_existente(str(pedido.nome_arquivo)):
            logger.warning(f"Pedido {pedido.numero_pedido_ol} não está registrado no banco de dados MySQL")
            continue

        if verifica_dados_pedido(pedido.numero_pedido_ol):
            atualizar_dados_pedido(pedido, TipoStatusOper.TRANSMITIDO.value)

        logger.info(f"Gerando cancelamento do pedido {pedido.numero_pedido_ol}")

        # Só gera se o pedido ainda está como este serviço o deixou: se a geração
        # manual (ou outra execução) pegou o pedido nesse meio-tempo, pula.
        if not reservar_status_pedido(pedido.numero_pedido_ol, TipoStatusOper.GERANDO_CANCELAMENTO.value,
                                      status_esperado=TipoStatusOper.AGUARDANDO_CANCELAMENTO.value):
            logger.warning(f"Pedido {pedido.numero_pedido_ol} mudou de status ou já está em geração — pulando.")
            continue
        LayouFactory.gerar_cancelado(industria, pedido)


if __name__ == "__main__":
    inicializar_processo(_SERVICO, pasta_da_aplicacao(__file__))

    atualizar_status_servico(_SERVICO, "Executando")
    try:
        # Sem CNPJ do distribuidor nenhum arquivo pode ser gerado: para antes de
        # tocar em qualquer pedido (o except abaixo marca o serviço com o motivo).
        exigir_cnpj_distribuidor()
        for industria in industrias_ativas():
            processar_industria(industria)

        atualizar_status_servico(_SERVICO, "OK", "Geração de cancelados foi concluída")
    except Exception as e:
        logger.error(f"[{_SERVICO}] Erro: {e}")
        atualizar_status_servico(_SERVICO, "Erro", str(e))
