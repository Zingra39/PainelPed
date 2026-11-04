from ol_core.core.logger import logger


def trata_textos(texto: str, direcao: str, tamanho: int, preenchimento: str = "0"):
    """
        Remove todos os caracteres não numéricos e não alfabeticos de uma string.
    """
    try:
        # Converte texto para string
        texto = str(texto)
    
        if direcao == 'r':
            return ''.join(c for c in texto if c.isalnum()).rjust(tamanho, preenchimento)
        elif direcao == 'l':
            return ''.join(c for c in texto if c.isalnum()).ljust(tamanho, preenchimento)
        else:
            return ''.join(c for c in texto if c.isalnum())
    except Exception as err:
        logger.error(f"Erro ao tratar texto {texto}: {err}")
        return "<Error>"

def preencher_com_zeros(quantidade: int) -> str:
    """
        Retorna cadeia de 0 com base na quantidade inserida
        Ex: 5 -> "00000"
        Ex: 10 -> "0000000000"
        

        :param quantidade: Quantidade de caracteres que a cadeia deve possuir
        :return: Cadeia de caracteres com 00
    """

    return "0" * quantidade
