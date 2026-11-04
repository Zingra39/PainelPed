/**
 * Dispara o download de um Blob no navegador: cria uma URL de objeto, um
 * `<a download>` temporário, simula o clique e libera a URL depois.
 *
 * Extraído para cá porque essa mesma sequência estava reimplementada em 3
 * lugares (`api/pedidos.ts` tinha a versão "oficial" `_baixarBlob`, usada só
 * por `exportConfeccao`/`exportRastreamento`; `gerarPedido`, no mesmo
 * arquivo, e `arquivosApi.download`, em `api/arquivos.ts`, reimplementavam a
 * mesma coisa na mão) — task #48.
 */
export function baixarBlob(blob: Blob, nomeArquivo: string): void {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = nomeArquivo
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}
