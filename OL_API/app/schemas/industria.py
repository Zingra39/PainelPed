from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class IndustriaFtpInput(BaseModel):
    ftp_pedidos: Optional[str] = None
    ftp_retornos: Optional[str] = None
    ftp_espelhos: Optional[str] = None
    ftp_cancelados: Optional[str] = None
    ftp_estoques: Optional[str] = None


class IndustriaFtpResponse(IndustriaFtpInput):
    model_config = {"from_attributes": True}


class IndustriaFornecedorItem(BaseModel):
    """Código do fornecedor no ERP do cliente (+ um rótulo opcional)."""
    cod_fornecedor: int = Field(gt=0)
    descricao: Optional[str] = Field(default=None, max_length=100)

    model_config = {"from_attributes": True}

    @field_validator("descricao")
    @classmethod
    def _limpa(cls, v: Optional[str]) -> Optional[str]:
        return (v or "").strip() or None


def _sem_codigo_repetido(itens: Optional[list[IndustriaFornecedorItem]]):
    if itens:
        codigos = [i.cod_fornecedor for i in itens]
        repetidos = sorted({c for c in codigos if codigos.count(c) > 1})
        if repetidos:
            raise ValueError(f"Código de fornecedor repetido: {', '.join(map(str, repetidos))}.")
    return itens


class IndustriaListItem(BaseModel):
    id: int
    nome: Optional[str]
    cnpj: Optional[str]
    layout: Optional[str]
    ativo: bool
    tem_ftp: bool

    model_config = {"from_attributes": True}


class IndustriaCreate(BaseModel):
    nome: str
    cnpj: Optional[str] = None
    layout: Optional[str] = None
    id_bbs: Optional[int] = None
    cond_mae: Optional[int] = None
    ativo: bool = True

    pasta_envio: Optional[str] = None
    pasta_entrada: Optional[str] = None
    pasta_retorno: Optional[str] = None
    pasta_espelho: Optional[str] = None
    pasta_cancelamento: Optional[str] = None
    pasta_backup_pedido: Optional[str] = None
    pasta_retorno_envio: Optional[str] = None
    pasta_retorno_espelho: Optional[str] = None
    pasta_pedido_original: Optional[str] = None
    pasta_envio_cancelamento: Optional[str] = None
    pasta_estoque: Optional[str] = None

    ftp: Optional[IndustriaFtpInput] = None
    fornecedores: Optional[list[IndustriaFornecedorItem]] = None

    _fornecedores_unicos = field_validator("fornecedores")(_sem_codigo_repetido)


class IndustriaUpdate(BaseModel):
    nome: Optional[str] = None
    cnpj: Optional[str] = None
    layout: Optional[str] = None
    id_bbs: Optional[int] = None
    cond_mae: Optional[int] = None
    ativo: Optional[bool] = None

    pasta_envio: Optional[str] = None
    pasta_entrada: Optional[str] = None
    pasta_retorno: Optional[str] = None
    pasta_espelho: Optional[str] = None
    pasta_cancelamento: Optional[str] = None
    pasta_backup_pedido: Optional[str] = None
    pasta_retorno_envio: Optional[str] = None
    pasta_retorno_espelho: Optional[str] = None
    pasta_pedido_original: Optional[str] = None
    pasta_envio_cancelamento: Optional[str] = None
    pasta_estoque: Optional[str] = None

    ftp: Optional[IndustriaFtpInput] = None
    # Lista completa: substitui a cadastrada. Omitido = não mexe.
    fornecedores: Optional[list[IndustriaFornecedorItem]] = None

    _fornecedores_unicos = field_validator("fornecedores")(_sem_codigo_repetido)


class IndustriaResponse(BaseModel):
    id: int
    nome: Optional[str]
    cnpj: Optional[str]
    layout: Optional[str]
    id_bbs: Optional[int]
    cond_mae: Optional[int]
    ativo: bool
    criado_em: Optional[datetime]
    atualizado_em: Optional[datetime]

    pasta_envio: Optional[str]
    pasta_entrada: Optional[str]
    pasta_retorno: Optional[str]
    pasta_espelho: Optional[str]
    pasta_cancelamento: Optional[str]
    pasta_backup_pedido: Optional[str]
    pasta_retorno_envio: Optional[str]
    pasta_retorno_espelho: Optional[str]
    pasta_pedido_original: Optional[str]
    pasta_envio_cancelamento: Optional[str]
    pasta_estoque: Optional[str]

    ftp: Optional[IndustriaFtpResponse] = None
    fornecedores: list[IndustriaFornecedorItem] = []

    model_config = {"from_attributes": True}
