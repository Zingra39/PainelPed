from datetime import datetime
from ol_core.models.erro import Erro, RESOLVIDO_IGNORADO
from ol_core.models.enums.tipo_severidade import TipoSeveridade
from ol_core.database.mysql.contexto_parametros import parametro_esta_ativo
from ol_core.database.mysql.contexto_ocorrencias import registrar_ocorrencia
from ol_core.database.sqlserver.contexto_cliente import resgatar_condicao, verifica_cliente_na_condicao


CONDICAO_CADASTRADA="CONDICAO_CADASTRADA"
CONDICAO_VALIDA="CONDICAO_VALIDA"
CONDICAO_SEM_DATA_VALIDADE="CONDICAO_SEM_DATA_VALIDADE"
VERIFICA_SE_BBS_ESTA_FLAGADO="VERIFICA_SE_BBS_ESTA_FLAGADO"
VERIFICA_SE_ACESSESIVEL_PARA_OUTRAS_FLAGADO="VERIFICA_SE_ACESSESIVEL_PARA_OUTRAS_FLAGADO"
VERIFICA_SE_ACESSA_OUTRAS_COND_NA_MAE_ESTA_FLAGADO="VERIFICA_SE_ACESSA_OUTRAS_COND_NA_MAE_ESTA_FLAGADO"
IGNORAR_CLIENTE_NAO_CADASTRADO_NA_CONDICAO="IGNORAR_CLIENTE_NAO_CADASTRADO_NA_CONDICAO"


def valida_condicaos(id_cond: int, cnpj_cliente: str, numero_pedido_ol: str):
    condicao = resgatar_condicao(id_cond)

    # Verifica se condição está no delage
    if condicao is None:
        erro = Erro(
            numero_pedido_ol=numero_pedido_ol,
            descricao=f"Condição {id_cond} não está cadastrada no Delage: {numero_pedido_ol}",
            criado_em=datetime.now(),
            severidade=TipoSeveridade.ERRO.value,
            resolvido=0
        )
        
        if parametro_esta_ativo(CONDICAO_CADASTRADA):
            erro.resolvido = RESOLVIDO_IGNORADO
            erro.severidade = TipoSeveridade.IGNORADO.value
        
        registrar_ocorrencia(erro)
        return
    else:
        # Verifica se a condição está ativa ainda (apenas data, sem horário)
        if condicao['validade_condicao'] is None: 
            erro = Erro(
                numero_pedido_ol=numero_pedido_ol,
                descricao=f"Condição {condicao['cod_cond']} não possui data de validade: {numero_pedido_ol}",
                criado_em=datetime.now(),
                severidade=TipoSeveridade.ERRO.value,
                resolvido=0
            )
            
            if parametro_esta_ativo(CONDICAO_SEM_DATA_VALIDADE):
                erro.resolvido = RESOLVIDO_IGNORADO
                erro.severidade = TipoSeveridade.IGNORADO.value
                
            registrar_ocorrencia(erro)
            return
        
        data_validade = condicao['validade_condicao'].date()
        if data_validade is not None and data_validade < datetime.now().date():
            erro = Erro(
                numero_pedido_ol=numero_pedido_ol,
                descricao=f"Condição {condicao['cod_cond']} está expirada: {numero_pedido_ol}",
                criado_em=datetime.now(),
                severidade=TipoSeveridade.ALERTA.value,
                resolvido=0
            )
            
            if parametro_esta_ativo(CONDICAO_VALIDA):
                erro.resolvido = RESOLVIDO_IGNORADO
                erro.severidade = TipoSeveridade.IGNORADO.value
            
            registrar_ocorrencia(erro)

        # Verifica se flag BBS está ativa
        if condicao['bbs'] != -1:
            erro = Erro(
                numero_pedido_ol=numero_pedido_ol,
                descricao=f"Condição {condicao['cod_cond']} não está com a flag BBS ativa: {numero_pedido_ol}",
                severidade=TipoSeveridade.CRITICO.value,
                criado_em=datetime.now(),
                resolvido=0
            )
            
            if parametro_esta_ativo(VERIFICA_SE_BBS_ESTA_FLAGADO):
                erro.resolvido = RESOLVIDO_IGNORADO
                erro.severidade = TipoSeveridade.IGNORADO.value
            
            registrar_ocorrencia(erro)

        # Verifica se flag "c.acessivel_outras_cond" está ativa
        if condicao['acessivel_outras_cond'] != -1:
            erro = Erro(
                numero_pedido_ol=numero_pedido_ol,
                descricao=f"Condição {condicao['cod_cond']} não está com a flag acessivel_outras_cond ativa: {numero_pedido_ol}",
                criado_em=datetime.now(),
                severidade=TipoSeveridade.CRITICO.value,
                resolvido=0
            )
            
            if parametro_esta_ativo(VERIFICA_SE_ACESSESIVEL_PARA_OUTRAS_FLAGADO):
                erro.resolvido = RESOLVIDO_IGNORADO
                erro.severidade = TipoSeveridade.IGNORADO.value

            registrar_ocorrencia(erro)

        # Verifica se é condição mãe
        if id_cond == 3692:
            # Verifica se a flag acessa_outras_cond está ativa para a condição 3692
            if condicao['acessa_outras_cond'] != -1:
                erro = Erro(
                    numero_pedido_ol=numero_pedido_ol,
                    descricao=f"Condição {condicao['cod_cond']} não está com a flag acessa_outras_cond ativa: {numero_pedido_ol}",
                    criado_em=datetime.now(),
                    severidade=TipoSeveridade.CRITICO.value,
                    resolvido=0
                )
                
                if parametro_esta_ativo(VERIFICA_SE_ACESSA_OUTRAS_COND_NA_MAE_ESTA_FLAGADO):
                    erro.resolvido = RESOLVIDO_IGNORADO
                    erro.severidade = TipoSeveridade.IGNORADO.value
                
                registrar_ocorrencia(erro)

        # Verifica se a condição é para todos os clientes
        if condicao['todos_clientes'] != -1:
            if not verifica_cliente_na_condicao(condicao['cod_cond'], cnpj_cliente):
                erro = Erro(
                    numero_pedido_ol=numero_pedido_ol,
                    descricao=f"Cliente {cnpj_cliente} não está cadastrado na condição {condicao['cod_cond']}: {numero_pedido_ol}",
                    criado_em=datetime.now(),
                    severidade=TipoSeveridade.CRITICO.value,
                    resolvido=0
                )
                
                if parametro_esta_ativo(IGNORAR_CLIENTE_NAO_CADASTRADO_NA_CONDICAO):
                    erro.resolvido = RESOLVIDO_IGNORADO
                    erro.severidade = TipoSeveridade.IGNORADO.value
                
                registrar_ocorrencia(erro)
