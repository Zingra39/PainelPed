from ol_core.core.exceptions import ErroConexaoBanco
from datetime import datetime
from ol_core.models.erro import Erro, RESOLVIDO_IGNORADO
from ol_core.core.logger import logger
from ol_core.models.pedido import Pedido
from ol_core.validators.valida_produto import valida_produto
from ol_core.validators.valida_cliente import valida_clientes
from ol_core.models.enums.tipo_severidade import TipoSeveridade
from ol_core.database.mysql.contexto_parametros import parametro_esta_ativo
from ol_core.database.mysql.contexto_ocorrencias import registrar_ocorrencia
from ol_core.database.sqlserver.contexto_pedido import verificar_primeiro_pedido, verificar_valor_pedido_minimo

VALOR_MINIMO_PEDIDO="VALOR_MINIMO_PEDIDO"
MINIMO_NAO_CONFIGURADO="MINIMO_NAO_CONFIGURADO"

def valida_valor_total_pedido(pedido: Pedido, cond: int):
    try:
        data_hoje = datetime.now().strftime("%Y-%m-%d")
            
        if pedido.valor_total is None or pedido.cnpj_cliente is None or pedido.numero_pedido_ol is None:
            return None
        
        if not verificar_primeiro_pedido(pedido.cnpj_cliente, data_hoje):
            valor_minimo_cond = verificar_valor_pedido_minimo(cond)
            
            if valor_minimo_cond == 0.0:
                erro = Erro(
                    descricao = f"Minimo da condição não configurado ou não encontrado para a condição {cond}",
                    numero_pedido_ol=pedido.numero_pedido_ol,
                    resolvido=0,
                    severidade=TipoSeveridade.ALERTA.value,
                    criado_em=datetime.now(),
                )
                
                if parametro_esta_ativo(MINIMO_NAO_CONFIGURADO):
                    erro.resolvido = RESOLVIDO_IGNORADO
                    erro.severidade = TipoSeveridade.IGNORADO.value
                
                registrar_ocorrencia(erro)
                return None
            
            if pedido.valor_total < valor_minimo_cond:
                erro = Erro(
                    descricao = f"Valor total pedido está abaixo do mínimo configurado na condição {cond}",
                    numero_pedido_ol=pedido.numero_pedido_ol,
                    resolvido=0,
                    severidade=TipoSeveridade.INFO.value,
                    criado_em=datetime.now(),
                )
                
                if parametro_esta_ativo(VALOR_MINIMO_PEDIDO):
                    erro.resolvido = RESOLVIDO_IGNORADO
                    erro.severidade = TipoSeveridade.IGNORADO.value
                
                registrar_ocorrencia(erro)
    except ErroConexaoBanco:
        raise
    except Exception as err:
        logger.error(f"Erro ao validar valor total pedido {pedido}: {err}")
        
        if pedido.numero_pedido_ol is None:
            return 0
        
        erro = Erro(
            descricao = f"Erro ao validar valor total pedido {pedido}",
            numero_pedido_ol=pedido.numero_pedido_ol,
            resolvido=0,
            severidade=TipoSeveridade.ERRO.value,
            criado_em=datetime.now(),
        )
        registrar_ocorrencia(erro)

def valida_pedido(pedido: Pedido, id_cond_mae: int) -> None:
    try:
        valida_clientes(pedido)
        valida_valor_total_pedido(pedido, id_cond_mae)
        
        if pedido.numero_pedido_ol is None:
            logger.error(f"Erro ao validar pedido {pedido}: Número de pedido OL não informado.")
            return None
        
        valida_produto(pedido.numero_pedido_ol, pedido.itens)
    except ErroConexaoBanco:
        raise
    except Exception as err:
        logger.error(f"Erro ao validar pedido {pedido}: {err}")
        
        if pedido.numero_pedido_ol is None:
            return None
        
        erro = Erro(
            descricao = f"Erro ao validar pedido {pedido}",
            numero_pedido_ol=pedido.numero_pedido_ol,
            resolvido=0,
            severidade=TipoSeveridade.ERRO.value,
            criado_em=datetime.now(),
        )
        registrar_ocorrencia(erro)
