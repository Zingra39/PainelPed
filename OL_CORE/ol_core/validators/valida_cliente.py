from datetime import datetime
from ol_core.models.erro import Erro, RESOLVIDO_IGNORADO
from ol_core.models.pedido import Pedido
from ol_core.models.enums.tipo_severidade import TipoSeveridade
from ol_core.database.sqlserver.contexto_cliente import resgatar_cliente
from ol_core.database.mysql.contexto_parametros import parametro_esta_ativo
from ol_core.database.mysql.contexto_ocorrencias import registrar_ocorrencia

CLIENTE_NAO_CADASTRADO="CLIENTE_NAO_CADASTRADO"
SITUACAO_CLIENTE="SITUACAO_CLIENTE"
ALVARA_VENCIDO="ALVARA_VENCIDO"

def valida_clientes(pedido: Pedido) -> None:
    if pedido.cnpj_cliente is None:
        raise ValueError("CNPJ do cliente não informado.")

    if pedido.numero_pedido_ol is None:
        raise ValueError("Número do pedido não informado.")
    
    cliente = resgatar_cliente(pedido.cnpj_cliente)

    if cliente is None:
        erro = Erro(
            descricao = f"Cliente {pedido.cnpj_cliente} não está cadastrado no sistema",
            numero_pedido_ol=pedido.numero_pedido_ol,
            resolvido=0,
            severidade=TipoSeveridade.ERRO.value,
            criado_em=datetime.now(),
        )
        
        if parametro_esta_ativo(CLIENTE_NAO_CADASTRADO):
            erro.resolvido = RESOLVIDO_IGNORADO
            erro.severidade = TipoSeveridade.IGNORADO.value
        
        registrar_ocorrencia(erro)
    else:
        if cliente['situacao_entidade'].lower().strip() in ['bloqueado', 'inativo']:
            erro = Erro(
                descricao = f"Cliente {cliente['razao_social']} - {cliente['cnpj']} está bloqueado no sistema",
                numero_pedido_ol=pedido.numero_pedido_ol,
                resolvido=0,
                severidade=TipoSeveridade.ALERTA.value,
                criado_em=datetime.now(),
            )
            
            if parametro_esta_ativo(SITUACAO_CLIENTE):
                erro.resolvido = RESOLVIDO_IGNORADO
                erro.severidade = TipoSeveridade.IGNORADO.value
                
            registrar_ocorrencia(erro)
        
        alvara = cliente['vencimento_alvara']
        if alvara is not None and alvara < datetime.now():
            erro = Erro(
                descricao = f"Cliente {cliente['razao_social']} - {cliente['cnpj']} está com alvara vencido",
                numero_pedido_ol=pedido.numero_pedido_ol,
                resolvido=0,
                severidade=TipoSeveridade.ALERTA.value,
                criado_em=datetime.now(),
            )
            
            if parametro_esta_ativo(ALVARA_VENCIDO):
                erro.resolvido = RESOLVIDO_IGNORADO
                erro.severidade = TipoSeveridade.IGNORADO.value
            
            registrar_ocorrencia(erro)
            
            if not parametro_esta_ativo(ALVARA_VENCIDO): return
