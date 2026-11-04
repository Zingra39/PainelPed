from enum import Enum

class TipoStatusOper(Enum):
    BAIXADO = "Recebido" # Pedido que acabou de ser coletado
    
    IMPORTANDO = "Importando Pedido" # Pedido que está no processo de importação no sistema PainelOL
    IMPORTADO = "Importado" # Pedido que foi importado com sucesso para o sistema PainelOL
    
    VERIFICAR = "Verificar" # Pedido que está com alguma ocorrencia registrada

    # Pedido que um operador marcou manualmente como "em análise" na triagem
    # (ver pedido.id_usuario_analise / em_analise_desde). Enquanto estiver
    # neste status ele NÃO pode ser transmitido nem reprocessado em lote; ao
    # encerrar a análise o pedido é reprocessado e volta como Pronto/Verificar.
    # Valor sem acento de propósito, igual aos demais deste enum (histórico de
    # dano de charset em produção).
    EM_ANALISE = "Em Analise"

    AGUARDANDO_REPROCESSANDO = "Aguardando Reprocessamento" # Pedido que está aguardando reprocessamento
    REPROCESSANDO = "Reprocessando" # Pedido que está no processo de reprocessamento
    
    PRONTO = "Pronto" # Pedido que está pronto para ser transmitido para o DELAGE
    
    TRANSMITINDO = "Transmitindo" # Pedido que está sendo transmitido para o DELAGE
    TRANSMITIDO = "Transmitido" # Pedido que foi transmitido para o DELAGE
    
    AGUARDANDO_RETORNO = "Aguardando Retorno" # Pedido que está aguardando retorno do DELAGE
    GERANDO_RETORNO = "Retorno Sendo Gerado" # Pedido que está gerando retorno do DELAGE
    RETORNO = "Retorno Gerado" # Pedido que gerou arquivo de retorno
    
    AGUARDANDO_ESPELHO = "Aguardando Espelho" # Pedido que está aguardando espelho
    GERANDO_ESPELHO = "Espelho Sendo Gerado" # Pedido que está gerando espelho
    ESPELHO = "Espelho Gerado" # Pedido que gerou arquivo de espelho
    
    AGUARDANDO_CANCELAMENTO = "Aguardando Cancelamento" # Pedido que está aguardando cancelamento
    GERANDO_CANCELAMENTO = "Cancelamento Sendo Gerado" # Pedido que está gerando cancelamento
    CANCELADO = "Cancelamento Gerado" # Pedido que foi cancelado
    
    FALHA = "Falha" # Pedido que apresentou uma falha sistemica

    # Falhas especificas de cada etapa de geracao manual/automatica (Retorno,
    # Espelho, Cancelamento) — permitem saber qual operacao falhou, ao contrario
    # do FALHA generico acima (usado por reprocessamento/transmissao).
    FALHA_RETORNO = "Falha no Retorno" # Falha ao gerar o arquivo de retorno
    FALHA_ESPELHO = "Falha no Espelho" # Falha ao gerar o arquivo de espelho
    FALHA_CANCELAMENTO = "Falha no Cancelamento" # Falha ao gerar o arquivo de cancelamento
    
    FALHA_REPROCESSAMENTO = "Falha no Reprocessamento" # Falha ao reprocessar o pedido (ex.: arquivo original não encontrado)