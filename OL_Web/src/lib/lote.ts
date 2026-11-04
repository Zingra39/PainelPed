import type { LoteResultado } from '../types'
import { apiErr } from './apiError'

/**
 * Executa `fn` para cada id em paralelo e devolve o resultado no mesmo formato
 * das rotas de lote do backend (`LoteResultado`), para a tela tratar ações em
 * lote do cliente e do servidor do mesmo jeito (F3 da auditoria).
 *
 * `rotular` traduz o id para o que aparece nos detalhes (normalmente o nº do
 * pedido OL); sem ele, vai o próprio id.
 */
export async function executarEmLote(
  ids: number[],
  fn: (id: number) => Promise<unknown>,
  rotular: (id: number) => string = String,
): Promise<LoteResultado> {
  const resultados = await Promise.allSettled(ids.map((id) => fn(id)))
  const detalhes = resultados.map((r, i) => ({
    numero_pedido_ol: rotular(ids[i]),
    sucesso: r.status === 'fulfilled',
    mensagem: r.status === 'fulfilled' ? '' : apiErr(r.reason, 'Erro inesperado.'),
  }))
  const sucesso = detalhes.filter((d) => d.sucesso).length
  return { total: ids.length, sucesso, falha: ids.length - sucesso, detalhes }
}

/**
 * Frase curta de resumo de um lote, para o banner de feedback (F2). Quando o
 * lote tem um pedido só e ele falhou, mostra o motivo real do backend em vez
 * de uma mensagem genérica.
 *
 * `acao` é o substantivo da operação: "Reprocessamento", "Transmissão",
 * "Reenvio de retorno"...
 */
export function resumoLote(res: LoteResultado, acao: string): { ok: boolean; texto: string } {
  if (res.total === 0) return { ok: false, texto: `${acao}: nenhum pedido encontrado para o critério selecionado.` }
  if (res.falha === 0) return { ok: true, texto: `${acao} concluído(a) para ${res.sucesso} pedido(s).` }
  const motivo = res.detalhes.find((d) => !d.sucesso)?.mensagem
  if (res.sucesso === 0) {
    return {
      ok: false,
      texto: res.total === 1 && motivo ? motivo : `${acao}: falha em todos os ${res.total} pedido(s).`,
    }
  }
  return { ok: false, texto: `${acao}: ${res.sucesso} de ${res.total} pedido(s) com sucesso; ${res.falha} falharam.` }
}
