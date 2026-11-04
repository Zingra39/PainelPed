from ol_core.core.logger import logger
from ol_core.services.import_service import LayouFactory
from ol_core.layouts import Operacao, industria_suporta
from ol_core.core.variaveis_globais import industrias_ativas
from ol_core.database.mysql.contexto_parametros import exigir_cnpj_distribuidor
from ol_core.core.config import inicializar_processo, pasta_da_aplicacao
from ol_core.database.mysql.contexto_servico import atualizar_status_servico

_SERVICO = "envio_estoque"

if __name__ == "__main__":
    inicializar_processo(_SERVICO, pasta_da_aplicacao(__file__))

    try:
        # Sem CNPJ do distribuidor nenhum arquivo pode ser gerado: para antes de
        # tocar em qualquer pedido (o except abaixo marca o serviço com o motivo).
        exigir_cnpj_distribuidor()
        for industria in industrias_ativas():
            atualizar_status_servico(_SERVICO, "Executando")
            if industria_suporta(industria, Operacao.ESTOQUE):
                LayouFactory.gerar_estoque(industria, None)
        atualizar_status_servico(_SERVICO, "OK", "Envio de estoque concluído")
    except Exception as e:
        logger.error(f"[{_SERVICO}] Erro: {e}")
        atualizar_status_servico(_SERVICO, "Erro", str(e))
