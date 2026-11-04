from ol_core.database.mysql.contexto_industria import buscar_industrias_ativas
from ol_core.models.industria import Industria


def industrias_ativas() -> list[Industria]:
    """Indústrias ativas, consultadas na hora da chamada.

    Antes era a constante `lista_industriais`, preenchida por uma consulta ao
    banco no IMPORT deste módulo — antes de o processo carregar a própria
    configuração, e sem chance de tratar a falha. Chamar no início do
    processamento de cada serviço.
    """
    return buscar_industrias_ativas()
