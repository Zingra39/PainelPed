from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class OcorrenciaResumo(BaseModel):
    id: int
    id_pedido: Optional[int] = None
    numero_pedido_ol: Optional[str] = None
    severidade: Optional[str]
    codigo: Optional[str]
    descricao: Optional[str]
    resolvido: bool
    criado_em: Optional[datetime]

    model_config = {"from_attributes": True}


class ItemOcorrenciaResumo(BaseModel):
    id: int
    severidade: Optional[str]
    codigo: Optional[str]
    descricao: Optional[str]
    resolvido: bool
    criado_em: Optional[datetime]

    model_config = {"from_attributes": True}


class PedidoItemSchema(BaseModel):
    id: int
    ean: Optional[str]
    codigo_produto_erp: Optional[int]
    quantidade_solicitada: Optional[int]
    quantidade_atendida: Optional[int]
    preco: Optional[Decimal]
    desconto: Optional[Decimal]
    cod_motivo: Optional[int]
    status: Optional[str]
    ocorrencias: list[ItemOcorrenciaResumo] = []
    id_cond: Optional[int] = None
    model_config = {"from_attributes": True}


class ArquivoResumo(BaseModel):
    id: int
    id_pedido: Optional[int] = None
    numero_pedido_ol: Optional[str]
    nome: Optional[str]
    tipo: Optional[str]
    hash_md5: Optional[str]
    situacao: Optional[str]
    criado_em: Optional[datetime]

    model_config = {"from_attributes": True}


class HistoricoResumo(BaseModel):
    id: int
    acao: Optional[str]
    detalhe: Optional[str]
    usuario_nome: Optional[str]
    criado_em: Optional[datetime]

    model_config = {"from_attributes": True}


class PedidoListItem(BaseModel):
    id: int
    numero_pedido_ol: Optional[str]
    cnpj_cliente: Optional[str]
    condicao: Optional[str]
    status_operacional: Optional[str]
    status_erp: Optional[str]
    valor_total: Optional[Decimal]
    data_pedido: Optional[datetime]
    industria_nome: Optional[str]
    total_ocorrencias: int = 0
    total_ocorrencias_abertas: int = 0
    # "Em Analise": preenchidos só enquanto o pedido está nesse status.
    id_usuario_analise: Optional[int] = None
    em_analise_por: Optional[str] = None
    em_analise_desde: Optional[datetime] = None
    # Selo "Analisado": persiste depois que a análise encerra (ver Pedido.analisado_por).
    analisado_por: Optional[str] = None
    analisado_em: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PedidoDetail(BaseModel):
    id: int
    numero_pedido_ol: Optional[str]
    nome_arquivo: Optional[str]
    codigo_interno_erp: Optional[int]
    cnpj_cliente: Optional[str]
    condicao: Optional[str]
    observacao: Optional[str] = None
    status_operacional: Optional[str]
    status_erp: Optional[str]
    valor_total: Optional[Decimal]
    data_pedido: Optional[datetime]
    criado_em: Optional[datetime]
    atualizado_em: Optional[datetime]
    industria_nome: Optional[str]
    itens: list[PedidoItemSchema] = []
    ocorrencias: list[OcorrenciaResumo] = []
    arquivos: list[ArquivoResumo] = []
    historico: list[HistoricoResumo] = []
    # True quando o retorno não foi gerado até 1h após a transmissão — libera a
    # geração manual (regra única em operacoes.retorno_manual_liberado_por_atraso).
    retorno_manual_liberado: bool = False
    # Gerações manuais aceitas para o pedido (regra única em
    # operacoes.acoes_de_geracao_manual) — a tela só mostra o botão se True.
    pode_gerar_retorno: bool = False
    pode_gerar_espelho: bool = False
    pode_gerar_cancelamento: bool = False
    # Ver PaginatedPedidosConfeccao.envio_somente_pronto.
    envio_somente_pronto: bool = False
    # "Em Analise": ver PedidoListItem.
    id_usuario_analise: Optional[int] = None
    em_analise_por: Optional[str] = None
    em_analise_desde: Optional[datetime] = None
    # Selo "Analisado": persiste depois que a análise encerra (ver Pedido.analisado_por).
    analisado_por: Optional[str] = None
    analisado_em: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PaginatedPedidos(BaseModel):
    items: list[PedidoListItem]
    total: int
    page: int
    size: int
    pages: int


class PaginatedPedidosConfeccao(BaseModel):
    items: list[PedidoListItem]
    total: int
    page: int
    size: int
    pages: int
    contagem_por_status: dict[str, int] = {}
    # Parâmetro BLOQUEAR_ENVIO_PEDIDO_VERIFICAR ligado: só "Pronto" pode ser
    # transmitido manualmente. Vai na resposta porque o Operador Logístico (quem
    # transmite) não tem acesso a GET /parametros.
    envio_somente_pronto: bool = False


class PedidoRastreamentoItem(BaseModel):
    id: int
    numero_pedido_ol: Optional[str]
    cnpj_cliente: Optional[str]
    condicao: Optional[str]
    status_operacional: Optional[str]
    status_erp: Optional[str]
    valor_total: Optional[Decimal]
    data_pedido: Optional[datetime]
    industria_nome: Optional[str]
    total_ocorrencias: int = 0
    total_ocorrencias_abertas: int = 0
    retorno_status: Optional[str] = None
    espelho_status: Optional[str] = None
    cancelamento_status: Optional[str] = None
    falha_geral: bool = False
    # Ver PedidoDetail.retorno_manual_liberado e PedidoDetail.pode_gerar_*.
    retorno_manual_liberado: bool = False
    pode_gerar_retorno: bool = False
    pode_gerar_espelho: bool = False
    pode_gerar_cancelamento: bool = False
    # Só vem preenchido em pedido cancelado (ver Pedido.motivo_cancelamento).
    motivo_cancelamento: Optional[str] = None
    # Selo "Analisado": persiste depois que a análise encerra (ver Pedido.analisado_por).
    analisado_por: Optional[str] = None
    analisado_em: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PaginatedPedidosRastreamento(BaseModel):
    items: list[PedidoRastreamentoItem]
    total: int
    page: int
    size: int
    pages: int


class TituloSchema(BaseModel):
    codigo_titulo: Optional[int] = None
    numero_titulo: Optional[str] = None
    serie_nf: Optional[str] = None
    data_emissao: Optional[datetime] = None
    data_vencimento: Optional[datetime] = None
    codigo_situacao: Optional[str] = None
    data_cancelamento: Optional[datetime] = None
    quem_cancelou: Optional[str] = None
    chave_acesso: Optional[str] = None


class PedidoDetalheCompleto(PedidoDetail):
    titulo: Optional[TituloSchema] = None


class OperacaoResponse(BaseModel):
    sucesso: bool
    mensagem: str


class ObservacaoBody(BaseModel):
    """Observação digitada pelo operador na triagem.

    O limite de 100 vem do layout Close-Up: o campo ocupa as posições 87 a
    186 do cabeçalho (100 caracteres). O nome do autor é prefixado pelo
    backend, então o texto útil aqui é menor que 100 — a validação final
    (texto + autor <= 100) acontece no endpoint, que é quem conhece o
    usuário autenticado.
    """
    observacao: str = Field(default="", max_length=100)


class LoteBody(BaseModel):
    data_inicio: Optional[date] = None
    data_fim: Optional[date] = None
    cnpj_cliente: Optional[str] = None


class ReprocessarLoteBody(LoteBody):
    apenas_erro: bool = False


class TransmitirLoteBody(BaseModel):
    apenas_sem_ocorrencia: bool = False


class LoteResultItem(BaseModel):
    numero_pedido_ol: str
    sucesso: bool
    mensagem: str


class LoteResultado(BaseModel):
    total: int
    sucesso: int
    falha: int
    detalhes: list[LoteResultItem]


class ReenviarLoteBody(BaseModel):
    """Reenvio em massa de arquivos já gerados, a partir do Histórico.

    Dois modos de seleção, mutuamente exclusivos:

    - `ids`: pedidos escolhidos na tela (linha ou seleção múltipla);
    - período (`data_inicio` / `data_fim` + filtros opcionais): todos os
      pedidos do Histórico naquele recorte — o mesmo filtro da listagem, para
      o que é reenviado ser exatamente o que a tela mostra.

    `tipo` é sempre UM tipo (valores de TipoArquivo — retorno / espelho /
    cancelado — ou "cancelamento" como apelido). Não existe reenvio de "todos":
    o operador escolhe explicitamente o que vai sair, inclusive no modo período,
    porque reenvio escreve na pasta da indústria e no FTP.
    """
    ids: Optional[list[int]] = None
    data_inicio: Optional[date] = None
    data_fim: Optional[date] = None
    industria_nome: Optional[str] = None
    status_erp: Optional[str] = None
    tipo: str


class LotePreview(BaseModel):
    """Contagem de pedidos que seriam afetados por uma ação em lote, sem
    executar nenhuma ação — usada para a tela de confirmação antes do disparo."""
    total: int


class ReenvioPreview(BaseModel):
    """Contagem do reenvio por período, mais o teto vigente.

    `limite` vem do parâmetro `limitador_de_envio` (tela de Parametrização) e
    viaja junto com a contagem de propósito: a tela precisa dizer ao operador
    *qual* é o teto que ele estourou, e o teto pode mudar sem redeploy."""
    total: int
    limite: int
    excede: bool
