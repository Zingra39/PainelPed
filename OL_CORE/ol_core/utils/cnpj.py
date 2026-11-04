"""CNPJ nas consultas ao ERP.

O ERP grava `entidade_doc.numero` com máscara ("43.410.436/0001-61"), e as
consultas comparavam com `dbo.RetiraEspacos_E_CatacteresEspeciais(ed.numero)
= :cnpj`. Função escalar aplicada na COLUNA impede o SQL Server de usar índice
(a consulta vira varredura da tabela, chamando a função linha a linha).

Aqui fazemos o inverso: em vez de tirar a máscara da coluna, montamos no Python
as formas possíveis do valor procurado e comparamos a coluna crua —
`ed.numero IN (:cnpj, :cnpj_mascarado)` —, o que permite busca por índice.
"""


def somente_digitos(valor) -> str:
    """O mesmo que dbo.RetiraEspacos_E_CatacteresEspeciais: só os dígitos."""
    return "".join(c for c in str(valor or "") if c.isdigit())


def formatar_cnpj(valor) -> str:
    """'43410436000161' -> '43.410.436/0001-61'. Valor que não tem 14 dígitos
    volta só com os dígitos (não há máscara a aplicar)."""
    d = somente_digitos(valor)
    if len(d) != 14:
        return d
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"


def parametros_cnpj(valor, prefixo: str = "cnpj") -> dict[str, str]:
    """Parâmetros para `coluna IN (:{prefixo}, :{prefixo}_mascarado)`: o CNPJ
    só com dígitos e com máscara, cobrindo as duas formas gravadas no ERP."""
    return {prefixo: somente_digitos(valor), f"{prefixo}_mascarado": formatar_cnpj(valor)}
