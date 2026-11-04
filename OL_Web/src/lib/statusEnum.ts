/**
 * Normaliza valores de status que chegam da API como *repr* do enum Python
 * em vez do valor, ex.: "TipoStatusOper.TRANSMITIDO" -> "Transmitido".
 *
 * Causa raiz (card #42 do dashboard de auditoria / achado do Frontend):
 * `atualizar_dados_pedido` em `OL_CORE/.../contexto_pedidos.py` grava o
 * MEMBRO do enum no UPDATE em vez de `.value`, e o pymysql serializa com
 * str() — então a coluna `status_erp` guarda literalmente
 * "TipoStatusOper.TRANSMITIDO". Enquanto os registros antigos não forem
 * corrigidos no banco, a tela precisa exibir o rótulo legível.
 *
 * Espelha os membros de `TipoStatusOper` (OL_CORE). Membro desconhecido cai
 * num fallback que só formata o texto, para nunca mostrar o repr cru.
 */
const VALOR_POR_MEMBRO: Record<string, string> = {
  BAIXADO: 'Recebido',
  IMPORTANDO: 'Importando Pedido',
  IMPORTADO: 'Importado',
  VERIFICAR: 'Verificar',
  EM_ANALISE: 'Em Analise',
  REPROCESSANDO: 'Reprocessando',
  PRONTO: 'Pronto',
  TRANSMITINDO: 'Transmitindo',
  TRANSMITIDO: 'Transmitido',
  AGUARDANDO_RETORNO: 'Aguardando Retorno',
  GERANDO_RETORNO: 'Retorno Sendo Gerado',
  RETORNO: 'Retorno Gerado',
  AGUARDANDO_ESPELHO: 'Aguardando Espelho',
  GERANDO_ESPELHO: 'Espelho Sendo Gerado',
  ESPELHO: 'Espelho Gerado',
  AGUARDANDO_CANCELAMENTO: 'Aguardando Cancelamento',
  GERANDO_CANCELAMENTO: 'Cancelamento Sendo Gerado',
  CANCELADO: 'Cancelamento Gerado',
  FALHA: 'Falha',
}

/** Status gravado no banco → texto mostrado na tela. O valor de "Em Analise" é
 *  gravado sem acento de propósito (igual aos demais valores de TipoStatusOper,
 *  por causa do histórico de dano de charset em produção), mas na interface
 *  deve aparecer com acento. Só serve para EXIBIR: filtros e comparações
 *  continuam usando o valor cru ("Em Analise"). */
const ROTULO_EXIBICAO: Record<string, string> = {
  'Em Analise': 'Em Análise',
}

export function exibirStatus(status: string): string {
  return ROTULO_EXIBICAO[status] ?? status
}

const REPR_ENUM = /^TipoStatusOper\.([A-Z_]+)$/

export function rotuloStatus(status: string): string {
  const match = REPR_ENUM.exec(status.trim())
  if (!match) return status

  const membro = match[1]
  if (VALOR_POR_MEMBRO[membro]) return VALOR_POR_MEMBRO[membro]

  // Membro novo, ainda não mapeado: "ALGUM_STATUS" -> "Algum Status"
  return membro
    .toLowerCase()
    .split('_')
    .map((palavra) => palavra.charAt(0).toUpperCase() + palavra.slice(1))
    .join(' ')
}
