"""Gera arquivos de pedido aleatórios (layout Close-Up) para testar o importa_pedidos.

Só é usado em homologação. Os dados (clientes, produtos, preços, condições) vêm do
MySQL local; o arquivo segue as posições do Anexo I do manual Hypera Close-Up e do
parser em ol_core/utils/conversor.py (converter_arquivo_closeup).

Registros (posições 1-based, texto X(n) com espaços à direita, numérico 9(n) com zeros à esquerda):
  1 cabeçalho  247 colunas
  2 detalhe    120 colunas (um por item)
  3 rodapé      36 colunas
"""
import random
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from ol_core.database.mysql.contexto_parametros import cnpj_distribuidor  # type: ignore
from ol_core.core.conexao import buscar_todos, buscar_um  # type: ignore
from ol_core.core.logger import logger  # type: ignore

from ambiente_local import esta_em_ol_local

_MAX_ITENS = 8
_TENTATIVAS_NUMERO = 20


# ---------------------------------------------------------------- formatação posicional

def _x(valor, tamanho: int) -> str:
    """Campo alfanumérico X(n): espaços à direita, truncado em n."""
    return str(valor if valor is not None else "")[:tamanho].ljust(tamanho)


def _n(valor, tamanho: int) -> str:
    """Campo numérico 9(n): zeros à esquerda."""
    texto = str(int(valor or 0))
    if len(texto) > tamanho:
        raise ValueError(f"Valor {valor} não cabe em 9({tamanho})")
    return texto.zfill(tamanho)


def _decimal(valor, tamanho: int, limite: Decimal) -> str:
    """Campo 9(n,2): n dígitos no total, 2 decimais implícitos, sem separador."""
    v = min(max(Decimal(str(valor or 0)), Decimal(0)), limite)
    return _n((v * 100).to_integral_value(), tamanho)


def monta_cabecalho(numero: str, cnpj_cliente: str, data: datetime, observacao: str) -> str:
    return (
        "1"                                              # 1     tipo do registro
        + _x(cnpj_cliente, 15)                           # 2     CNPJ da farmácia
        + _x(numero, 20)                                 # 17    número do pedido
        + data.strftime("%d%m%Y")                        # 37    data do pedido DDMMAAAA
        + "000"                                          # 45    vago
        + "E"                                            # 48    tipo da compra (Estadual)
        + "C"                                            # 49    tipo do retorno
        + "1"                                            # 50    linha de produto
        + "0"                                            # 51    compra integral
        + _x(cnpj_distribuidor() or "", 15)     # 52    CNPJ distribuidor
        + _x("", 20)                                     # 67    número OS
        + _x(observacao, 100)                            # 87    observação
        + _x("", 10)                                     # 187   código do representante
        + _x("", 6)                                      # 197   código da campanha
        + "0"                                            # 203   faturamento integral
        + _n(0, 3)                                       # 204   prazo
        + "0"                                            # 207   condição de prazo
        + _x("", 40)                                     # 208   código do prazo
    )


def monta_item(numero: str, ean: str, quantidade: int, id_cond: int, desconto, preco) -> str:
    cond = int(id_cond or 0)
    return (
        "2"                                              # 1     tipo do registro
        + _x(numero, 20)                                 # 2     número do pedido
        + _n(ean, 13)                                    # 22    EAN-13
        + _n(quantidade, 5)                              # 35    quantidade
        + _n(min(cond, 9999), 4)                         # 40    condição comercial
        + _decimal(desconto, 5, Decimal("99.99"))        # 44    desconto 9(5,2)
        + _n(0, 3)                                       # 49    prazo
        + "0"                                            # 52    condição de desconto
        + "0"                                            # 53    condição de prazo
        + _x("", 40)                                     # 54    código do prazo
        # 94: código da oferta 9(20). O parser lê o id da condição nas 5 primeiras
        # posições deste campo (conversor.py: linha[93:98]), então ele vai à esquerda.
        + _n(cond, 5).ljust(20, "0")
        + _decimal(preco, 7, Decimal("99999.99"))        # 114   preço 9(7,2)
    )


def monta_rodape(numero: str, qtd_itens: int, qtd_unidades: int) -> str:
    return "3" + _x(numero, 20) + _n(qtd_itens, 5) + _n(qtd_unidades, 10)


# ---------------------------------------------------------------- dados do MySQL

def _numero_pedido_inedito(data: datetime) -> str:
    """YYYYMMDD + 10 dígitos + origem 7 + laboratório P, sem colidir com pedido/arquivo."""
    for _ in range(_TENTATIVAS_NUMERO):
        numero = f"{data:%Y%m%d}{random.randint(0, 9_999_999_999):010d}7P"
        existe = buscar_um(
            "SELECT 1 AS x FROM pedido WHERE numero_pedido_ol = %s "
            "UNION SELECT 1 FROM arquivo WHERE nome LIKE %s",
            (numero, f"PEDIDO\\_{numero}\\_%"),
        )
        if not existe:
            return numero
    raise RuntimeError("Não foi possível gerar um número de pedido inédito.")


def _sortear_cliente() -> tuple[str, str]:
    row = buscar_um(
        "SELECT cnpj_cliente, observacao FROM pedido "
        "WHERE CHAR_LENGTH(cnpj_cliente) = 14 ORDER BY RAND() LIMIT 1"
    )
    if not row:
        raise RuntimeError("Sem pedidos no MySQL para sortear um cliente.")
    return row["cnpj_cliente"], (row["observacao"] or "")


def _sortear_itens(qtd: int) -> list[dict]:
    # Só EANs que já resolveram no ERP (preço e código de produto preenchidos).
    itens = buscar_todos(
        "SELECT ean, MAX(quantidade_solicitada) AS qtd, MAX(desconto) AS desconto, "
        "       MAX(id_cond) AS id_cond, MAX(preco) AS preco "
        "FROM pedido_item "
        "WHERE preco > 0 AND codigo_produto_erp > 0 AND CHAR_LENGTH(ean) = 13 "
        "GROUP BY ean ORDER BY RAND() LIMIT %s",
        (qtd,),
    )
    if not itens:
        raise RuntimeError("Sem itens no MySQL para montar o pedido de teste.")
    return itens


# ---------------------------------------------------------------- geração

def gerar_pedido_teste(industria) -> Path:
    """Gera um arquivo de pedido aleatório em industria.pasta_envio e devolve o caminho.

    A pasta de envio precisa estar dentro de OL_LOCAL (ver ambiente_local.isolar_industria);
    caso contrário nada é gravado.
    """
    pasta = industria.pasta_envio
    if not esta_em_ol_local(pasta):
        raise RuntimeError(f"Recusado: pasta de envio fora de OL_LOCAL ({pasta}).")

    agora = datetime.now()
    numero = _numero_pedido_inedito(agora)
    cnpj, observacao = _sortear_cliente()
    itens = _sortear_itens(random.randint(1, _MAX_ITENS))

    linhas = [monta_cabecalho(numero, cnpj, agora, observacao)]
    unidades = 0
    for item in itens:
        quantidade = random.randint(1, max(1, min(int(item["qtd"] or 1), 200)))
        unidades += quantidade
        linhas.append(monta_item(numero, item["ean"], quantidade, item["id_cond"],
                                 item["desconto"], item["preco"]))
    linhas.append(monta_rodape(numero, len(itens), unidades))

    caminho = Path(pasta) / f"PEDIDO_{numero}_{cnpj}.txt"
    caminho.write_text("\n".join(linhas) + "\n", encoding="utf-8", newline="")
    logger.info(f"[homologacao] Pedido de teste gerado: {caminho} ({len(itens)} itens)")
    return caminho
