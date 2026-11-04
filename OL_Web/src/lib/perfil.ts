/**
 * Comparação de nome de perfil — espelho de `_perfil_equivalente` em
 * OL_API/app/core/deps.py.
 *
 * O nome do perfil vem do banco (`perfil.nome`, via /auth/me) e era comparado
 * aqui com string crua: `user.perfil === 'Operador Logístico'`. Isso quebrou em
 * produção quando o nome ficou gravado como "Operador Log?stico" — um cliente
 * MySQL com charset errado converte o "í" em "?" — e o operador perdeu todos os
 * botões de ação, além de tomar 403 no backend pelo mesmo motivo.
 *
 * A comparação aqui tolera o que não muda o significado do perfil (acento,
 * caixa, espaço extra) e caractere destruído por conversão de charset, usando
 * as MESMAS regras do backend, para o front nunca divergir do que a API
 * autoriza.
 */

/** "?" do MySQL e U+FFFD do Unicode: o que sobra de uma letra que não pôde ser
 *  representada no charset de origem. */
const MARCAS_DANO_CHARSET = new Set(['?', '�'])

/** Nomes reais de perfil têm um ou dois acentos; o teto impede que um nome
 *  formado só por "?" case com qualquer perfil de mesmo tamanho. */
const MAX_CARACTERES_DANIFICADOS = 3

/** Sem acento, minúsculo, espaços colapsados. */
function normalizar(nome: string | null | undefined): string {
  if (!nome) return ''
  return nome
    .normalize('NFKD')
    .replace(/\p{M}/gu, '')
    .toLowerCase()
    .trim()
    .replace(/\s+/g, ' ')
}

/** True se o nome recebido do banco designa o mesmo perfil que o esperado. */
export function perfilEquivalente(
  recebido: string | null | undefined,
  esperado: string,
): boolean {
  const alvo = normalizar(esperado)
  const atual = normalizar(recebido)

  if (atual === alvo) return true
  if (atual.length !== alvo.length) return false

  const danificados = [...atual].filter((c) => MARCAS_DANO_CHARSET.has(c)).length
  if (danificados === 0 || danificados > MAX_CARACTERES_DANIFICADOS) return false
  // O dano tem de ser minoria do nome: o resto precisa identificar o perfil.
  if (danificados * 2 >= alvo.length) return false

  return [...atual].every(
    (c, i) => c === alvo[i] || MARCAS_DANO_CHARSET.has(c),
  )
}

/** True se o perfil recebido é algum dos aceitos. */
export function perfilEmAlgum(
  recebido: string | null | undefined,
  aceitos: string[],
): boolean {
  return aceitos.some((aceito) => perfilEquivalente(recebido, aceito))
}
