import os
from datetime import datetime
from ol_core.core.logger import logger
from ol_core.models.pedido import Pedido
from ol_core.models.arquivo import Arquivo
from ol_core.models.industria import Industria
from ol_core.models.pedido_item import Pedido_Item
from ol_core.models.enums.tipo_arquivo import TipoArquivo
from ol_core.utils.disparar import envia_arquivo_para_pasta
from ol_core.database.sqlserver.contexto_produto import resgatar_produto
from ol_core.layouts import formato_closeup as formato
# Codificação de desconto em 5 dígitos é formato do Close-Up; mantidas aqui
# por compatibilidade com quem já importa de ol_core.utils.conversor.
from ol_core.layouts.formato_closeup import converter_desconto_float_str, converter_desconto_str_float  # noqa: F401

def converter_data_banco(data: str) -> datetime:
    """
        Converte uma data em string para datetime.

        Args:
            data (str): A data em string, no formato 'YYYY-MM-DD HH:MM:SS'.

        Returns:
            datetime: A data convertida para datetime.
    """
    # converte manualmente
    timestamp = int(data)
    data_faturamento_extraido = datetime.utcfromtimestamp(timestamp)
    return data_faturamento_extraido

def extrair_data_pedido_do_numero(numero_pedido_ol: str) -> datetime:
    """
        Extrai a data de envio do pedido a partir dos 8 primeiros dígitos do
        número do pedido OL (formato YYYYMMDD).

        Ex.: "2026082800326672667P" -> 2026-08-28

        O número do pedido embute a data de envio nesses 8 primeiros dígitos
        (mesmo padrão visível no nome do arquivo, ex.:
        PEDIDO_2026082800326672667P_57107095000164.txt). Usamos essa data em
        vez de datetime.now() para que os filtros por período do dashboard
        reflitam a data real do pedido, e não o instante em que o arquivo foi
        processado (que pode ficar defasado em caso de atraso na coleta).

        Se o número não seguir o padrão esperado, faz fallback para
        datetime.now() e loga um aviso, para não travar a importação por
        causa de um formato inesperado.
    """
    if numero_pedido_ol:
        prefixo_data = numero_pedido_ol.strip()[:8]
        if len(prefixo_data) == 8 and prefixo_data.isdigit():
            try:
                return datetime.strptime(prefixo_data, "%Y%m%d")
            except ValueError:
                pass

    logger.error(
        f"Não foi possível extrair a data de envio a partir do número de pedido "
        f"'{numero_pedido_ol}'. Usando a data/hora atual como fallback."
    )
    return datetime.now()

def valida_numero_ol(numero_pedido_ol: str, arquivo: str) -> None:
    """
        Valida se o número do pedido OL no primeiro registro, é igual
        ao numero pedido OL do nome do arquivo

        Args:
            numero_pedido_ol (str): O número do pedido OL a ser validado.
            arquivo (str): Nome do arquivo a ser validado.
    """

    nome_arquivo = os.path.basename(arquivo)

    # Ex.: PEDIDO_2026082800326672667P_57107095000164.txt -> 2026082800326672667P
    numero_pedido_ol_arquivo = formato.numero_pedido_do_nome_arquivo(nome_arquivo)

    if numero_pedido_ol != numero_pedido_ol_arquivo:
        raise ValueError(
            f"O número do pedido OL '{numero_pedido_ol}' no primeiro registro "
            f"não corresponde ao número do pedido OL '{numero_pedido_ol_arquivo}' "
            f"no nome do arquivo '{nome_arquivo}'."
        )


def converter_arquivo_closeup(industria: Industria, arquivo: str) -> Pedido | None:
    """
        Converte um arquivo em formato string para um objeto Pedido.

        Args:
            arquivo (str): O conteúdo do arquivo em formato string.

        Returns:
            Pedido: O objeto Pedido convertido a partir do arquivo.
    """
    try:
        # Abre arquivo e extrai conteúdo
        with open(arquivo, 'r', encoding='utf-8') as f:
            linhas = f.readlines()

        # Valida se arquivo contém informações de itens
        if len(linhas) <= 2 or len(linhas) <= 0:
            logger.error("O arquivo deve conter pelo menos uma linha de cabeçalho e uma linha de item.")

            if not industria.pasta_erro:
                logger.error(f"A pasta de erros não foi configurada para {industria.nome}.")
                return None

            envia_arquivo_para_pasta(arquivo, industria.pasta_erro)
            return None

        # Processa a primeira linha para extrair os dados do pedido (posições: formato_closeup)
        cabecalho = formato.ler_cabecalho_pedido(linhas[0])
        cnpj_cliente = cabecalho["cnpj_cliente"]
        numero_pedido = cabecalho["numero_pedido_ol"]
        data_pedido = extrair_data_pedido_do_numero(numero_pedido)
        observacao = cabecalho["observacao"]

        valida_numero_ol(numero_pedido, arquivo)

        # Cria o objeto Pedido com os dados extraídos
        # nome_arquivo guarda só o nome do arquivo (não o caminho completo) —
        # é usado como identificador/lookup (inclusive contra o nome_arquivo
        # do ERP), nunca para abrir o arquivo em disco (isso usa a tabela
        # `arquivo`, que já guarda caminho completo separadamente).
        pedido = Pedido(
            nome_arquivo=os.path.basename(arquivo),
            cnpj_cliente=cnpj_cliente.strip(),
            numero_pedido_ol=numero_pedido,
            data_pedido=str(data_pedido),
            observacao=observacao,
            id_cond=industria.cond_mae,
            itens=[]
        )

        # Processa todas as linhas, menos a primeira e a ultima, para extrair os dados dos itens do pedido
        for linha in linhas[1:-1:]:
            dados_item = formato.ler_item_pedido(linha)
            ean = dados_item["ean"]
            numero_pedido_ol = dados_item["numero_pedido_ol"]
            quantidade_solicitada = dados_item["quantidade_solicitada"]
            desconto = dados_item["desconto"]
            id_cond = dados_item["id_cond"]  # None se não veio escrito

            item_db = resgatar_produto(ean)

            if item_db is None:
                preco = 0
                codigo_produto = 0
            else:
                preco = item_db['preco']
                codigo_produto = item_db['codigo_produto']

            item = Pedido_Item(
                numero_pedido_ol=numero_pedido_ol,
                cnpj_cliente=cnpj_cliente.strip(),
                ean=ean,
                quantidade_solicitada=quantidade_solicitada,
                desconto=desconto,
                id_cond=id_cond or 0,
                preco=preco,
                quantidade_atendida=0,
                codigo_produto=codigo_produto
            )

            pedido.itens.append(item)

        return pedido
    except Exception as err:
        logger.error(f"Erro ao converter arquivo {arquivo}: {err}")
        return None

def converter_arquivo_para_objeto(numero_pedido_ol: str, arquivo: str) -> Arquivo:
    """
        Converte um arquivo em formato string para um objeto Arquivo.

        Args:
            arquivo (str): O conteúdo do arquivo em formato string.

        Returns:
            Arquivo: O objeto Arquivo convertido a partir do arquivo.
    """

    nome = os.path.basename(arquivo)
    tipo = TipoArquivo.PEDIDO.value
    hash = None
    caminho = arquivo
    situacao = "PENDENTE"
    # criado_em reflete a data de envio do pedido (extraída do número do
    # pedido OL), não o instante do processamento — ver extrair_data_pedido_do_numero.
    criado_em = extrair_data_pedido_do_numero(numero_pedido_ol)

    return Arquivo(
        numero_pedido_ol=numero_pedido_ol,
        nome=nome,
        tipo=tipo,
        hash=hash or "",
        caminho=caminho,
        situacao=situacao,
        criado_em=criado_em
    )
