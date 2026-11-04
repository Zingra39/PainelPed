import logging
from pathlib import Path

from ol_core.models.enums.tipo_layout import TipoLayout


class Industria:
    def __init__(
        self,
        id_industria: int,
        nome: str,
        tipo_layout: TipoLayout,
        cnpj: str = "",
        id_bbs: int = 0,
        ativo: bool = True,
        cond_mae: int = 0,

        # Pastas DispFarm
        pasta_envio: str = "",
        pasta_envio_retorno: str = "",
        pasta_envio_nf: str = "",
        pasta_envio_cancelamento: str = "",

        # Pastas ERP
        pasta_pedido_original: str = "",
        pasta_entrada: str = "",
        pasta_retorno: str = "",
        pasta_nfe: str = "",
        pasta_backup: str = "",
        pasta_cancelamento: str = "",
        pasta_estoque: str = "",
        pasta_erro: str = "",
    ):
        self.id_industria = id_industria
        self.nome = nome
        self.tipo_layout = tipo_layout
        self.cnpj = cnpj
        self.id_bbs = id_bbs
        self.ativo = ativo
        self.cond_mae = cond_mae

        # Pastas DispFarm
        self.pasta_envio = Path(pasta_envio) if pasta_envio else None
        self.pasta_envio_retorno = Path(pasta_envio_retorno) if pasta_envio_retorno else None
        self.pasta_envio_nf = Path(pasta_envio_nf) if pasta_envio_nf else None
        self.pasta_envio_cancelamento = Path(pasta_envio_cancelamento) if pasta_envio_cancelamento else None

        # Pastas ERP
        self.pasta_pedido_original = Path(pasta_pedido_original) if pasta_pedido_original else None
        self.pasta_entrada = Path(pasta_entrada) if pasta_entrada else None
        self.pasta_retorno = Path(pasta_retorno) if pasta_retorno else None
        self.pasta_nfe = Path(pasta_nfe) if pasta_nfe else None
        self.pasta_backup = Path(pasta_backup) if pasta_backup else None
        self.pasta_cancelamento = Path(pasta_cancelamento) if pasta_cancelamento else None
        self.pasta_estoque = Path(pasta_estoque) if pasta_estoque else None
        self.pasta_erro = Path(pasta_erro) if pasta_erro else None

        self._criar_pastas()

    @classmethod
    def from_db(cls, row: dict) -> "Industria":
        return cls(
            id_industria=row["id"],
            nome=row["nome"],
            tipo_layout=TipoLayout(row["tipo_layout"]),
            cnpj=row.get("cnpj", ""),
            id_bbs=row.get("id_bbs", 0),
            ativo=bool(row.get("ativo", True)),
            cond_mae=row.get("cond_mae", 0),
            pasta_envio=row.get("pasta_envio", ""),
            pasta_envio_retorno=row.get("pasta_envio_retorno", ""),
            pasta_envio_nf=row.get("pasta_envio_nf", ""),
            pasta_envio_cancelamento=row.get("pasta_envio_cancelamento", ""),
            pasta_pedido_original=row.get("pasta_pedido_original", ""),
            pasta_entrada=row.get("pasta_entrada", ""),
            pasta_retorno=row.get("pasta_retorno", ""),
            pasta_nfe=row.get("pasta_nfe", ""),
            pasta_backup=row.get("pasta_backup", ""),
            pasta_cancelamento=row.get("pasta_cancelamento", ""),
            pasta_estoque=row.get("pasta_estoque", ""),
            pasta_erro=row.get("pasta_erro", ""),
        )

    def _criar_pastas(self):
        pastas = [
            self.pasta_envio,
            self.pasta_envio_retorno,
            self.pasta_envio_nf,
            self.pasta_envio_cancelamento,
            self.pasta_pedido_original,
            self.pasta_entrada,
            self.pasta_retorno,
            self.pasta_nfe,
            self.pasta_backup,
            self.pasta_cancelamento,
            self.pasta_estoque,
            self.pasta_erro,
        ]
        for pasta in pastas:
            if pasta is None:
                continue
            try:
                pasta.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                logging.warning(f"Não foi possível criar pasta {pasta}: {e}")
