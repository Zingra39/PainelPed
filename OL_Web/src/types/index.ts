export interface Perfil {
  id: number
  nome: string
}

export interface Usuario {
  id: number
  nome: string | null
  email: string | null
  perfil_nome: string | null
  id_perfil: number | null
  ativo: boolean
  ultimo_acesso: string | null
  criado_em: string | null
}

export interface AuthUser {
  id: number
  nome: string
  email: string
  perfil: string
  ativo: boolean
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

// ── Pedidos ────────────────────────────────────────────
export interface PedidoListItem {
  id: number
  numero_pedido_ol: string
  cnpj_cliente: string
  condicao: string | null
  status_operacional: string
  status_erp: string
  valor_total: number | null
  data_pedido: string | null
  industria_nome: string
  total_ocorrencias: number
  total_ocorrencias_abertas: number
  /** "Em Analise": preenchidos só enquanto o pedido está nesse status. */
  id_usuario_analise?: number | null
  em_analise_por?: string | null
  em_analise_desde?: string | null
  /** Selo "Analisado": persiste depois que a análise encerra (última análise). */
  analisado_por?: string | null
  analisado_em?: string | null
}

export interface Arquivo {
  id: number
  id_pedido: number | null
  numero_pedido_ol: string | null
  nome: string | null
  tipo: string | null
  hash_md5: string | null
  situacao: string | null
  criado_em: string | null
}

export interface OcorrenciaItem {
  id: number
  severidade: string | null
  codigo: string | null
  descricao: string | null
  resolvido: boolean
  criado_em: string | null
}

export interface PedidoItemDetalhado {
  id: number
  ean: string | null
  codigo_produto_erp: number | null
  quantidade_solicitada: number | null
  quantidade_atendida: number | null
  preco: number | null
  desconto: number | null
  cod_motivo: number | null
  status: string | null
  id_cond: number | null
  ocorrencias: OcorrenciaItem[]
}

export interface OcorrenciaPedido {
  id: number
  id_pedido: number | null
  numero_pedido_ol: string | null
  severidade: string | null
  codigo: string | null
  descricao: string | null
  resolvido: boolean
  criado_em: string | null
}

export interface HistoricoResumo {
  id: number
  acao: string | null
  detalhe: string | null
  usuario_nome: string | null
  criado_em: string | null
}

export interface TituloInfo {
  codigo_titulo: number | null
  numero_titulo: string | null
  serie_nf: string | null
  data_emissao: string | null
  data_vencimento: string | null
  codigo_situacao: string | null
  data_cancelamento: string | null
  quem_cancelou: string | null
  chave_acesso: string | null
}

export interface PedidoDetalheCompleto {
  id: number
  numero_pedido_ol: string | null
  nome_arquivo: string | null
  codigo_interno_erp: number | null
  cnpj_cliente: string | null
  condicao: string | null
  observacao: string | null
  status_operacional: string | null
  status_erp: string | null
  valor_total: number | null
  data_pedido: string | null
  criado_em: string | null
  atualizado_em: string | null
  industria_nome: string | null
  itens: PedidoItemDetalhado[]
  ocorrencias: OcorrenciaPedido[]
  arquivos: Arquivo[]
  historico: HistoricoResumo[]
  titulo: TituloInfo | null
  /** Retorno não gerado até 1h após a transmissão — libera a geração manual. */
  retorno_manual_liberado?: boolean
  /** Gerações manuais aceitas (regra da API: operacoes.acoes_de_geracao_manual). */
  pode_gerar_retorno?: boolean
  pode_gerar_espelho?: boolean
  pode_gerar_cancelamento?: boolean
  /** Parâmetro BLOQUEAR_ENVIO_PEDIDO_VERIFICAR ligado: só "Pronto" pode ser transmitido manualmente. */
  envio_somente_pronto?: boolean
  /** "Em Analise": preenchidos só enquanto o pedido está nesse status. */
  id_usuario_analise?: number | null
  em_analise_por?: string | null
  em_analise_desde?: string | null
  /** Selo "Analisado": persiste depois que a análise encerra (última análise). */
  analisado_por?: string | null
  analisado_em?: string | null
}

// kept for backward compat with /pedidos/{id}
export interface PedidoDetail {
  id: number
  numero_pedido_ol: string | null
  nome_arquivo: string | null
  codigo_interno_erp: number | null
  cnpj_cliente: string | null
  condicao: string | null
  observacao: string | null
  status_operacional: string | null
  status_erp: string | null
  valor_total: number | null
  data_pedido: string | null
  criado_em: string | null
  atualizado_em: string | null
  industria_nome: string | null
  itens: PedidoItemDetalhado[]
  ocorrencias: OcorrenciaPedido[]
  arquivos: Arquivo[]
  historico: HistoricoResumo[]
}

export interface LoteResultItem {
  numero_pedido_ol: string
  sucesso: boolean
  mensagem: string
}

/** Resposta das ações de um pedido só (retorno, espelho, reprocessar,
 *  transmitir, análise, observação, cancelamento) — `OperacaoResponse` em
 *  OL_API/app/schemas/pedido.py. */
export interface OperacaoResponse {
  sucesso: boolean
  mensagem: string
}

export interface LoteResultado {
  total: number
  sucesso: number
  falha: number
  detalhes: LoteResultItem[]
}

/** Contagem de quantos pedidos uma ação em lote afetaria, sem executá-la —
 *  usada pela tela de confirmação antes do disparo. */
export interface LotePreview {
  total: number
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  size: number
  pages: number
}

export type ContagemPorStatus = Record<string, number>

export interface PaginatedConfeccao extends PaginatedResponse<PedidoListItem> {
  contagem_por_status: ContagemPorStatus
  /** Parâmetro BLOQUEAR_ENVIO_PEDIDO_VERIFICAR ligado: só "Pronto" pode ser transmitido manualmente. */
  envio_somente_pronto?: boolean
}

export interface PedidoRastreamentoItem {
  id: number
  numero_pedido_ol: string
  cnpj_cliente: string
  condicao: string | null
  status_operacional: string
  status_erp: string
  valor_total: number | null
  data_pedido: string | null
  industria_nome: string
  total_ocorrencias: number
  total_ocorrencias_abertas: number
  retorno_status: string | null
  espelho_status: string | null
  cancelamento_status: string | null
  falha_geral: boolean
  /** Retorno não gerado até 1h após a transmissão — libera a geração manual. */
  retorno_manual_liberado?: boolean
  /** Gerações manuais aceitas (regra da API: operacoes.acoes_de_geracao_manual). */
  pode_gerar_retorno?: boolean
  pode_gerar_espelho?: boolean
  pode_gerar_cancelamento?: boolean
  /** Motivo real do cancelamento, vindo do ERP. Só vem em pedido cancelado. */
  motivo_cancelamento: string | null
  /** Selo "Analisado": persiste depois que a análise encerra (última análise). */
  analisado_por?: string | null
  analisado_em?: string | null
}

// ── Dashboard ──────────────────────────────────────────
/** Intervalo "de / até" do dashboard — ambas no formato YYYY-MM-DD, e o
 *  recorte é sempre pela data do pedido (Pedido.data_pedido no backend). */
export interface PeriodoFiltro {
  data_inicio: string
  data_fim: string
}

export interface DashboardCards {
  total_recebidos: number
  total_importados: number
  total_pendentes: number
  total_prontos_transmissao: number
  total_retornos_gerados: number
  total_espelhos_gerados: number
  total_cancelamentos_gerados: number
}

export interface MotivoCancelamentoItem {
  motivo: string
  total: number
}

export interface ArquivosPorDiaItem {
  data: string
  retorno: number
  espelho: number
  cancelamento: number
}

export interface PedidosFaturadosPorDiaItem {
  data: string
  total: number
}

export interface TopProdutoItem {
  ean: string
  descricao: string | null
  quantidade_solicitada: number
}

// ── Indústrias ─────────────────────────────────────────
export interface IndustriaFtp {
  ftp_pedidos: string | null
  ftp_retornos: string | null
  ftp_espelhos: string | null
  ftp_cancelados: string | null
  ftp_estoques: string | null
}

export interface IndustriaListItem {
  id: number
  nome: string | null
  cnpj: string | null
  layout: string | null
  ativo: boolean
  tem_ftp: boolean
}

export interface Industria {
  id: number
  nome: string | null
  cnpj: string | null
  layout: string | null
  id_bbs: number | null
  cond_mae: number | null
  ativo: boolean
  criado_em: string | null
  atualizado_em: string | null

  pasta_envio: string | null
  pasta_entrada: string | null
  pasta_retorno: string | null
  pasta_espelho: string | null
  pasta_cancelamento: string | null
  pasta_backup_pedido: string | null
  pasta_retorno_envio: string | null
  pasta_retorno_espelho: string | null
  pasta_pedido_original: string | null
  pasta_envio_cancelamento: string | null
  pasta_estoque: string | null

  ftp: IndustriaFtp | null
  /** Códigos do fornecedor no ERP do cliente — filtram o arquivo de estoque. */
  fornecedores: IndustriaFornecedor[]
}

export interface IndustriaFornecedor {
  cod_fornecedor: number
  descricao: string | null
}

// ── Erros ──────────────────────────────────────────────
export interface ErroItem {
  id: number
  codigo_erp: number | null
  descricao: string | null
}

// ── Serviços ───────────────────────────────────────────
export interface Servico {
  id: number
  nome: string
  status: string | null
  mensagem: string | null
  ultimo_heartbeat: string | null
  timeout_minutos: number
  online: boolean
}

// ── Parametrização ─────────────────────────────────────
export interface Parametro {
  id: number
  chave: string
  valor: string | null
  descricao: string | null
  atualizado_em: string | null
  /** Nome de quem alterou por último — null se nunca foi alterado. */
  atualizado_por: string | null
}

/** Configuração obrigatória ainda não preenchida (GET /parametros/pendencias). */
export interface PendenciaConfiguracao {
  chave: string
  titulo: string
  mensagem: string
}
