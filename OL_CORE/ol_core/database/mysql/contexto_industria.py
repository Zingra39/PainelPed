from ol_core.core.exceptions import ErroConexaoBanco
from ol_core.core.logger import logger
from ol_core.core.conexao import buscar_todos, buscar_um
from ol_core.models.industria import Industria


def buscar_industrias_ativas() -> list[Industria]:
    try:
        rows = buscar_todos("SELECT * FROM industria WHERE ativo = 1")
        return [Industria.from_db(row) for row in rows]
    except ErroConexaoBanco:
        raise
    except Exception as e:
        logger.error(f"[buscar_industrias_ativas] {e}")
        return []


def buscar_industria_ftp(id_industria: int) -> dict | None:
    try:
        return buscar_um(
            "SELECT * FROM industria_ftp WHERE fk_id_industria = %s",
            (id_industria,)
        )
    except ErroConexaoBanco:
        raise
    except Exception as e:
        logger.error(f"[buscar_industria_ftp] {e}")
        return None


def buscar_fornecedores_industria(id_industria: int) -> list[int]:
    """Códigos do fornecedor no ERP associados à indústria (seção "Fornecedores
    no ERP" do cadastro). Filtram os produtos do arquivo de estoque."""
    try:
        rows = buscar_todos(
            "SELECT cod_fornecedor FROM industria_fornecedor WHERE fk_id_industria = %s ORDER BY cod_fornecedor",
            (id_industria,),
        )
        return [int(r["cod_fornecedor"]) for r in rows]
    except ErroConexaoBanco:
        raise
    except Exception as e:
        logger.error(f"[buscar_fornecedores_industria] {e}")
        return []
