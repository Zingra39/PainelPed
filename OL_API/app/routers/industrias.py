from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.database import get_db
from app.core.deps import require_perfis
from app.models import Industria, IndustriaFornecedor, IndustriaFtp, Pedido
from app.schemas.industria import (
    IndustriaCreate,
    IndustriaFornecedorItem,
    IndustriaFtpInput,
    IndustriaListItem,
    IndustriaResponse,
    IndustriaUpdate,
)

router = APIRouter(prefix="/industrias", tags=["Indústrias"])

_ADMIN = require_perfis("Administrador")

_PASTA_FIELDS = (
    "pasta_envio", "pasta_entrada", "pasta_retorno", "pasta_espelho",
    "pasta_cancelamento", "pasta_backup_pedido", "pasta_retorno_envio",
    "pasta_retorno_espelho", "pasta_pedido_original", "pasta_envio_cancelamento",
    "pasta_estoque",
)


def _upsert_ftp(db: Session, industria: Industria, ftp_in: IndustriaFtpInput) -> None:
    ftp = industria.ftp
    if not ftp:
        ftp = IndustriaFtp(fk_id_industria=industria.id)
        db.add(ftp)
        industria.ftp = ftp
    for campo, valor in ftp_in.model_dump(exclude_unset=True).items():
        setattr(ftp, campo, valor)


def _substituir_fornecedores(industria: Industria, itens: list[IndustriaFornecedorItem]) -> None:
    """Deixa a indústria com exatamente esta lista de códigos. Reaproveita a
    linha de um código que continua (só atualiza a descrição) em vez de apagar
    e reinserir — reinserir o mesmo código no mesmo flush violaria a chave
    única (fk_id_industria, cod_fornecedor)."""
    atuais = {f.cod_fornecedor: f for f in industria.fornecedores}
    nova_lista = []
    for item in itens:
        linha = atuais.get(item.cod_fornecedor) or IndustriaFornecedor(cod_fornecedor=item.cod_fornecedor)
        linha.descricao = item.descricao
        nova_lista.append(linha)
    industria.fornecedores = nova_lista  # os que saíram são apagados (delete-orphan)


@router.get("", response_model=list[IndustriaListItem])
def listar_industrias(
    ativo: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    _user=Depends(_ADMIN),
):
    q = db.query(Industria).options(joinedload(Industria.ftp))
    if ativo is not None:
        q = q.filter(Industria.ativo == ativo)
    industrias = q.order_by(Industria.nome).all()
    return [
        IndustriaListItem(
            id=i.id, nome=i.nome, cnpj=i.cnpj, layout=i.layout,
            ativo=bool(i.ativo), tem_ftp=i.ftp is not None,
        )
        for i in industrias
    ]


@router.get("/{id}", response_model=IndustriaResponse)
def detalhe_industria(id: int, db: Session = Depends(get_db), _user=Depends(_ADMIN)):
    industria = (
        db.query(Industria)
        .options(joinedload(Industria.ftp), selectinload(Industria.fornecedores))
        .filter(Industria.id == id)
        .first()
    )
    if not industria:
        raise HTTPException(status_code=404, detail="Indústria não encontrada.")
    return industria


@router.post("", response_model=IndustriaResponse, status_code=201)
def criar_industria(body: IndustriaCreate, db: Session = Depends(get_db), _user=Depends(_ADMIN)):
    if body.cnpj and db.query(Industria).filter(Industria.cnpj == body.cnpj).first():
        raise HTTPException(status_code=409, detail="CNPJ já cadastrado para outra indústria.")

    dados = body.model_dump(exclude={"ftp", "fornecedores"})
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    nova = Industria(**dados, criado_em=now, atualizado_em=now)
    db.add(nova)
    db.flush()

    if body.ftp:
        _upsert_ftp(db, nova, body.ftp)
    if body.fornecedores:
        _substituir_fornecedores(nova, body.fornecedores)

    db.commit()
    db.refresh(nova)
    return nova


@router.put("/{id}", response_model=IndustriaResponse)
def atualizar_industria(
    id: int,
    body: IndustriaUpdate,
    db: Session = Depends(get_db),
    _user=Depends(_ADMIN),
):
    industria = (
        db.query(Industria)
        .options(joinedload(Industria.ftp), selectinload(Industria.fornecedores))
        .filter(Industria.id == id)
        .first()
    )
    if not industria:
        raise HTTPException(status_code=404, detail="Indústria não encontrada.")

    if body.cnpj and body.cnpj != industria.cnpj:
        if db.query(Industria).filter(Industria.cnpj == body.cnpj, Industria.id != id).first():
            raise HTTPException(status_code=409, detail="CNPJ já cadastrado para outra indústria.")

    dados = body.model_dump(exclude_unset=True, exclude={"ftp", "fornecedores"})
    for campo, valor in dados.items():
        setattr(industria, campo, valor)

    if body.ftp:
        _upsert_ftp(db, industria, body.ftp)
    if body.fornecedores is not None:
        _substituir_fornecedores(industria, body.fornecedores)

    industria.atualizado_em = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    db.refresh(industria)
    return industria


@router.delete("/{id}", status_code=204)
def excluir_industria(id: int, db: Session = Depends(get_db), _user=Depends(_ADMIN)):
    industria = db.query(Industria).filter(Industria.id == id).first()
    if not industria:
        raise HTTPException(status_code=404, detail="Indústria não encontrada.")

    tem_pedidos = db.query(Pedido.id).filter(Pedido.id_industria == id).first() is not None
    if tem_pedidos:
        raise HTTPException(
            status_code=409,
            detail="Não é possível excluir: há pedidos vinculados a esta indústria. Desative-a em vez disso.",
        )

    db.delete(industria)
    db.commit()
