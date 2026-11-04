"""Formato dos arquivos do layout Close-Up (Hypera): só texto, sem I/O.

Aqui ficam as posições, larguras e preenchimentos de cada linha — o contrato
com a indústria. Nada aqui consulta banco, ERP, FTP ou disco: os services
(`retorno_service`, `espelho_service`, `cancelamento_service`,
`estoque_service`) e o `utils/conversor` buscam os dados, validam e chamam
estas funções para montar ou ler o texto. Os golden files em
OL_TEST/golden/closeup/ travam o resultado byte a byte.

Este módulo não importa nada do resto do ol_core além de `utils.tratamento`,
para poder ser usado pelos services sem ciclo de importação.
"""
from datetime import datetime

from ol_core.utils.tratamento import preencher_com_zeros, trata_textos

# Arquivo de estoque tem nome fixo (não depende de pedido).
NOME_ARQUIVO_ESTOQUE = "ESTOQUE_P_HYPERA_CAC.TXT"


# ------------------------------------------------------------------ nomes de arquivo

def nome_arquivo_retorno(numero_pedido_ol: str, cnpj_cliente: str) -> str:
    return f"RETORNO_{numero_pedido_ol}_{cnpj_cliente}.TXT"


def nome_arquivo_espelho(numero_pedido_ol: str, cnpj_cliente: str) -> str:
    return f"ESPELHO_{numero_pedido_ol}_{cnpj_cliente}.TXT"


def nome_arquivo_cancelamento(numero_pedido_ol: str, cnpj_cliente: str) -> str:
    return f"CANCELAMENTO_{numero_pedido_ol}_{cnpj_cliente}.TXT"


def cnpj_do_nome_arquivo(nome_arquivo: str) -> str | None:
    """CNPJ do cliente no nome do arquivo de pedido (PEDIDO_<numero>_<cnpj>.txt),
    com 14 dígitos. None se o nome não tiver a terceira parte."""
    partes = nome_arquivo.split("_")
    if len(partes) <= 2:
        return None
    return partes[2].replace(".txt", "").rjust(14, "0")


def numero_pedido_do_nome_arquivo(nome_arquivo: str) -> str:
    """Ex.: PEDIDO_2026082800326672667P_57107095000164.txt -> 2026082800326672667P"""
    return nome_arquivo.split("_")[1].split(".")[0]


# ------------------------------------------------------------------ desconto (5 dígitos)

def converter_desconto_str_float(valor: str) -> float:
    """"08666" -> 86.66 (três dígitos inteiros e dois decimais)."""
    if len(valor) != 5:
        raise ValueError("A string deve conter exatamente 5 caracteres para ser convertida.")
    return float(valor[:3] + "." + valor[3:])


def converter_desconto_float_str(valor: float) -> str:
    """86.66 -> "08666"."""
    return str(int(round(valor * 100))).rjust(5, "0")


# ------------------------------------------------------------------ arquivo de pedido

# Observação no cabeçalho do pedido: posições 87 a 186 (1-based) -> [86:186].
OBSERVACAO_INICIO = 86
OBSERVACAO_TAMANHO = 100
OBSERVACAO_FIM = OBSERVACAO_INICIO + OBSERVACAO_TAMANHO


def ler_cabecalho_pedido(linha: str) -> dict:
    """Linha 1 do arquivo de pedido. O CNPJ vem cru (15 posições, sem strip)."""
    return {
        "cnpj_cliente": linha[1:16],
        "numero_pedido_ol": linha[16:36],
        "observacao": linha[OBSERVACAO_INICIO:OBSERVACAO_FIM].strip(),
    }


def aplicar_observacao(cabecalho: str, observacao: str) -> str:
    """Grava a observação no cabeçalho do pedido (sem a quebra de linha).
    A linha é completada com espaços até o fim do campo antes de fatiar, senão
    um cabeçalho mais curto que o layout truncaria a observação."""
    cabecalho = cabecalho.ljust(OBSERVACAO_FIM)
    return (
        cabecalho[:OBSERVACAO_INICIO]
        + observacao[:OBSERVACAO_TAMANHO].ljust(OBSERVACAO_TAMANHO)
        + cabecalho[OBSERVACAO_FIM:]
    )


def reconstruir_arquivo_pedido(numero_pedido_ol, cnpj_cliente, data_pedido: datetime, observacao,
                               itens: list[tuple]) -> str:
    """Arquivo de pedido remontado a partir do banco, quando o original não está
    mais em disco. itens: (ean, quantidade solicitada, desconto, id_cond).

    Reproduz exatamente o que a API sempre gerou — inclusive as divergências em
    relação ao manual oficial documentadas (xfail) em
    OL_TEST/api/test_gerar_pedido_router.py e o CNPJ do distribuidor fixo."""
    numero = (numero_pedido_ol or "").ljust(20)
    cnpj = (cnpj_cliente or "").ljust(15)
    observacao_valor = str(observacao) if observacao is not None else ""

    linhas = [
        f"1{cnpj}{numero}{data_pedido.strftime('%d%m%Y')}000EC8046239901000131{' ' * 21}"
        f"{observacao_valor if observacao_valor else ' '}"
    ]
    for ean, quantidade, desconto, id_cond in itens:
        # posições 39:43 e 48:93 não são armazenadas — preenchidas com zeros/espaços
        linhas.append(
            f"2{numero}{str(ean or '').rjust(13, '0')}{str(quantidade or 0).rjust(5, '0')}0000"
            f"{converter_desconto_float_str(float(desconto or 0))}{' ' * 45}{id_cond}"
        )
    linhas.append(f"3{numero}{str(len(linhas) + 1).rjust(5, '0')}{str(len(itens)).rjust(5, '0')}")
    return "\r\n".join(linhas) + "\r\n"


def ler_item_pedido(linha: str) -> dict:
    """Linha de item (todas entre o cabeçalho e o rodapé). id_cond None se em branco."""
    id_cond = int(linha[93:98]) if linha[93:98].strip() != "" else None
    return {
        "numero_pedido_ol": linha[1:21],
        "ean": linha[21:34],
        "quantidade_solicitada": int(linha[34:39]),
        "desconto": converter_desconto_str_float(linha[43:48]),
        "id_cond": id_cond,
    }


# ------------------------------------------------------------------ retorno e espelho

def conteudo_arquivo(cabecalho: str, linhas_itens: list[str], rodape: str) -> str:
    """Retorno, espelho: uma linha por registro, todas terminadas em quebra de linha."""
    return "".join(linha + "\n" for linha in [cabecalho, *linhas_itens, rodape])


def rodape(numero_pedido_ol: str, qtd_linhas: int, qtd_atendida: int, qtd_nao_atendida: int) -> str:
    """Linha tipo 3 do retorno e do espelho. qtd_linhas conta cabeçalho e rodapé."""
    return (
        f"3{numero_pedido_ol}"
        f"{trata_textos(str(qtd_linhas), 'r', 5, '0')}"
        f"{trata_textos(str(qtd_atendida), 'r', 5, '0')}"
        f"{trata_textos(str(qtd_nao_atendida), 'r', 5, '0')}"
        f"{preencher_com_zeros(14)}"
    )


def cabecalho_retorno(cnpj_cliente: str, numero_pedido_ol: str, data_processamento: datetime,
                      codigo_interno_pedido, cnpj_distribuidor: str) -> str:
    return (
        f"1{trata_textos(cnpj_cliente, 'l', 15, ' ')}{numero_pedido_ol}"
        f"{trata_textos(data_processamento.strftime('%d%m%Y'), 'l', 8, '0')}0"
        f"{trata_textos(data_processamento.strftime('%H%M%S'), 'l', 8, '0')}"
        f"{trata_textos(str(codigo_interno_pedido), 'r', 12, '0')}"
        f"{preencher_com_zeros(10)}{cnpj_distribuidor}"
    )


def linha_item_retorno(ean: str, numero_pedido_ol: str, qtd_atendida: int, desconto: float,
                       qtd_nao_atendida: int, cod_motivo) -> str:
    return (
        f"2{trata_textos(ean, 'r', 13, '0')}{numero_pedido_ol}"
        f"{trata_textos(str(qtd_atendida), 'r', 5, '0')}"
        f"{trata_textos(converter_desconto_float_str(round(desconto, 2)), 'r', 5, '0')}"
        f"{preencher_com_zeros(3)}"
        f"{trata_textos(str(qtd_nao_atendida), 'r', 5, '0')}"
        f"{trata_textos(str(cod_motivo), 'l', 50, ' ')}"
    )


def cabecalho_espelho(cnpj_cliente: str, numero_pedido_ol: str, data_emissao: datetime,
                      codigo_pedido_interno: int, data_vencimento: datetime, cnpj_distribuidor: str) -> str:
    return (
        f"1{trata_textos(cnpj_cliente, 'l', 15, ' ')}{numero_pedido_ol}"
        f"{data_emissao.strftime('%d%m%Y')}Z{data_emissao.strftime('%H%M%S%f')[:-4]}"
        f"{str(codigo_pedido_interno).rjust(12, '0')}{preencher_com_zeros(2)}"
        f"{data_vencimento.strftime('%d%m%Y')}{cnpj_distribuidor}"
    )


def dados_nf_espelho(numero_titulo, serie_nf, data_emissao: datetime, chave_acesso) -> str:
    """Trecho da NF repetido em todas as linhas de item: nº, série, emissão, chave."""
    return (
        f"{trata_textos(numero_titulo, 'r', 12, '0')}"
        f"{trata_textos(str(serie_nf), 'r', 3, '0')}"
        f"{data_emissao.strftime('%d%m%Y')}"
        f"{trata_textos(chave_acesso, 'r', 44, ' ')}"
    )


def linha_item_espelho(ean: str, numero_pedido_ol: str, qtd_atendida: int, desconto: float,
                       qtd_nao_atendida: int, cod_motivo, dados_nf: str, valor_liquido_total: float) -> str:
    return (
        f"2{trata_textos(ean, 'r', 13, '0')}{numero_pedido_ol}"
        f"{trata_textos(str(qtd_atendida), 'r', 5, '0')}"
        f"{trata_textos(converter_desconto_float_str(round(desconto, 2)), 'r', 5, '0')}"
        f"{preencher_com_zeros(3)}"
        f"{trata_textos(str(qtd_nao_atendida), 'r', 5, '0')}"
        f"{trata_textos(str(cod_motivo), 'l', 50, ' ')}"
        f"{dados_nf}"
        f"{trata_textos(converter_desconto_float_str(valor_liquido_total), 'r', 10, ' ')}"
        f"{preencher_com_zeros(3)}"
    )


# ------------------------------------------------------------------ cancelamento

def conteudo_cancelamento(cnpj_distribuidor: str, cnpj_cliente: str, numero_pedido_ol: str,
                          itens: list[tuple[str, int, object]], data_cancelamento: str) -> str:
    """itens: (ean, quantidade solicitada, código de motivo). data_cancelamento
    já no formato do arquivo (ddmmaaaaHHMMSS)."""
    linhas = [
        f"1{trata_textos(cnpj_distribuidor, 'r', 14, '0')}",
        f"2{trata_textos(cnpj_cliente, 'l', 15, ' ')}",
        f"3{trata_textos(numero_pedido_ol, 'r', 20, '0')}",
        *(
            f"4  {trata_textos(ean, 'r', 13, '0')}{trata_textos(str(qtd), 'r', 8, '0')}{cod_motivo}"
            for ean, qtd, cod_motivo in itens
        ),
        f"5{data_cancelamento}",
    ]
    return "".join(linha + "\n" for linha in linhas)


def data_cancelamento_do_arquivo(data: datetime) -> str:
    return data.strftime("%d%m%Y%H%M%S")


# ------------------------------------------------------------------ estoque

def primeira_linha_estoque(cnpj_distribuidor: str, data_criacao: datetime) -> str:
    return f"1{cnpj_distribuidor}{data_criacao.strftime('%d%m%Y%H%M')}"


def registro_estoque(cod_barra: str, estoque: str) -> str:
    """Concatenação estrita de propósito: valor nulo do ERP (NaN) levanta
    TypeError em vez de virar o texto "nan" no arquivo da indústria."""
    return "2" + cod_barra + estoque


# No arquivo de estoque a última linha NÃO termina em quebra de linha (sempre foi
# assim): primeira_linha + "\n" + registros unidos por "\n".
