from datetime import datetime, timedelta
from ol_core.core.logger import logger # type: ignore
from ol_core.models.enums.tipo_status_oper import TipoStatusOper
from ol_core.services.import_service import LayouFactory # type: ignore
from ol_core.layouts import Operacao, industria_suporta
from ol_core.core.variaveis_globais import industrias_ativas # type: ignore
from ol_core.database.mysql.contexto_parametros import exigir_cnpj_distribuidor
from ol_core.core.config import inicializar_processo, pasta_da_aplicacao
from ol_core.database.mysql.contexto_servico import atualizar_status_servico # type: ignore
from ol_core.database.mysql.contexto_arquivo import verificar_espelho_existente # type: ignore
from ol_core.database.sqlserver.contexto_titulo import verificar_emissao_titulos # type: ignore
from ol_core.database.mysql.contexto_pedidos import atualizar_status_pedido, reservar_status_pedido, verifica_dados_pedido, verifica_pedido_existente # type: ignore

_SERVICO = "espelhos"

def atualizar_status_para_aguardando(pedidos: list) -> list:
    pedido_com_numero_ol = []
    for pedido in pedidos:
        if pedido.numero_pedido_ol is None:
            logger.error(f"Pedido {pedido.nome_arquivo} não possui número de pedido ol")
            continue

        id_arquivo = verificar_espelho_existente(pedido.numero_pedido_ol)
        if id_arquivo is not None:
            logger.warning("Arquivo de Espelho já foi gerado")
            continue

        else:
            # Não sobrescreve um pedido em geração (ex.: geração manual pelo
            # painel em andamento) — UPDATE condicional atômico.
            if reservar_status_pedido(pedido.numero_pedido_ol, TipoStatusOper.AGUARDANDO_ESPELHO.value):
                pedido_com_numero_ol.append(pedido)
            else:
                logger.warning(f"Pedido {pedido.numero_pedido_ol} já está em geração — pulando.")
    return pedido_com_numero_ol


def processar_industria(industria) -> None:
    # Layout sem espelho: nenhum pedido é tocado.
    if not industria_suporta(industria, Operacao.ESPELHO):
        return

    data_atual = datetime.now() - timedelta(days=5)
    titulos = verificar_emissao_titulos(industria.id_bbs, data_atual.strftime("%Y-%m-%d"))

    if titulos:
        titulos = atualizar_status_para_aguardando(titulos)

    if titulos is None:
        logger.warning("Nenhum título foi encontrado para gerar espelho")
        return

    for titulo in titulos:
        if not verifica_pedido_existente(str(titulo.nome_arquivo)):
            logger.warning(f"Pedido {titulo.numero_pedido_ol} não está registrado no banco de dados MySQL")
            continue

        if not verifica_dados_pedido(titulo.numero_pedido_ol):
            logger.warning(f"Pedido {titulo.numero_pedido_ol} não possui dados de pedido válidos")
            continue

        # Só gera se o pedido ainda está como este serviço o deixou: se a geração
        # manual (ou outra execução) pegou o pedido nesse meio-tempo, pula.
        if not reservar_status_pedido(titulo.numero_pedido_ol, TipoStatusOper.GERANDO_ESPELHO.value,
                                      status_esperado=TipoStatusOper.AGUARDANDO_ESPELHO.value):
            logger.warning(f"Pedido {titulo.numero_pedido_ol} mudou de status ou já está em geração — pulando.")
            continue
        LayouFactory.gerar_espelho(industria, titulo)


if __name__ == "__main__":
    inicializar_processo(_SERVICO, pasta_da_aplicacao(__file__))
    try:
        # Sem CNPJ do distribuidor nenhum arquivo pode ser gerado: para antes de
        # tocar em qualquer pedido (o except abaixo marca o serviço com o motivo).
        exigir_cnpj_distribuidor()
        atualizar_status_servico(_SERVICO, "Executando")
        for industria in industrias_ativas():
            processar_industria(industria)

        atualizar_status_servico(_SERVICO, "OK", "Geração de espelhos concluída")
    except Exception as e:
        logger.error(f"[{_SERVICO}] Erro: {e}")
        atualizar_status_servico(_SERVICO, "Erro", str(e))
