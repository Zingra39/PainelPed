/**
 * Formato mínimo de uma resposta de erro do axios, usado só para extrair a
 * mensagem que o backend manda em `response.data.detail`.
 *
 * Extraído para cá porque esse par (tipo + função) estava duplicado,
 * caractere por caractere, em 6 arquivos (Confeccao.tsx, PedidoDetail.tsx,
 * Rastreamento.tsx, Usuarios.tsx, Industrias/IndustriaDetail.tsx,
 * Industrias/IndustriasList.tsx) — task #48.
 */
export type ApiLike = { response?: { data?: { detail?: unknown } } }

/** Extrai `response.data.detail` de um erro de requisição; cai para
 * `fallback` quando a resposta não tiver esse campo ou ele não for string. */
export function apiErr(e: unknown, fallback: string): string {
  const d = (e as ApiLike).response?.data?.detail
  return typeof d === 'string' ? d : fallback
}

/**
 * Mesma ideia do `apiErr`, para requisições feitas com `responseType: 'blob'`
 * (os exports). Nessas, o axios entrega o corpo do erro como Blob — inclusive
 * o JSON de erro do backend —, então `response.data.detail` é `undefined` e o
 * `apiErr` cairia sempre no fallback, escondendo o motivo real.
 */
export async function apiErrBlob(e: unknown, fallback: string): Promise<string> {
  const data = (e as { response?: { data?: unknown } }).response?.data
  if (data instanceof Blob) {
    try {
      const texto = await data.text()
      const detail = (JSON.parse(texto) as { detail?: unknown }).detail
      if (typeof detail === 'string') return detail
      // FastAPI manda erro de validação como lista de objetos; aí o texto cru
      // não ajuda o operador — melhor o fallback.
    } catch {
      // Corpo não era JSON (ex.: HTML de proxy). Fallback.
    }
    return fallback
  }
  return apiErr(e, fallback)
}
