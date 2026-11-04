from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.deps import get_current_user, require_perfis
from app.models import Parametro
from app.schemas.parametro import ParametroResponse, ParametroUpdate, PendenciaConfiguracao

router = APIRouter(prefix="/parametros", tags=["Parametrização"])

# Tela de parametrização é liberada só pra Administrador e Gerente Comercial
# (definido na criação do Card) — diferente do escopo de /usuarios, que é só
# Administrador.
_ACESSO = require_perfis("Administrador", "Gerente Comercial")


def _to_response(p: Parametro) -> ParametroResponse:
    return ParametroResponse(
        id=p.id,
        chave=p.chave,
        valor=p.valor,
        descricao=p.descricao,
        atualizado_em=p.atualizado_em,
        atualizado_por=p.atualizado_por.nome if p.atualizado_por else None,
    )


CHAVE_CNPJ_DISTRIBUIDOR = "cnpj_distribuidor"
CHAVE_FILIAIS_ESTOQUE = "filiais_estoque"


def cnpj_valido(cnpj: str) -> bool:
    """14 dígitos, não todos iguais, com os dois dígitos verificadores certos."""
    if len(cnpj) != 14 or not cnpj.isdigit() or len(set(cnpj)) == 1:
        return False

    def digito(base: str) -> str:
        pesos = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2][-len(base):]
        resto = sum(int(d) * p for d, p in zip(base, pesos)) % 11
        return "0" if resto < 2 else str(11 - resto)

    return cnpj[12] == digito(cnpj[:12]) and cnpj[13] == digito(cnpj[:13])


def normalizar_valor(chave: str, valor: str) -> str | None:
    """Valida e normaliza o valor de um parâmetro antes de gravar. Devolve
    None para "não configurado" (só onde a chave permite). ValueError = 422."""
    if chave == CHAVE_CNPJ_DISTRIBUIDOR:
        digitos = "".join(c for c in valor if c.isdigit())
        if not cnpj_valido(digitos):
            raise ValueError("CNPJ do distribuidor inválido: informe os 14 dígitos de um CNPJ válido.")
        return digitos

    if chave == CHAVE_FILIAIS_ESTOQUE:
        partes = [p for p in valor.replace(";", ",").replace(" ", ",").split(",") if p.strip()]
        filiais: list[int] = []
        for parte in partes:
            if not parte.strip().isdigit() or int(parte) <= 0:
                raise ValueError(f"Código de filial inválido: '{parte.strip()}'. Use números separados por vírgula.")
            if int(parte) not in filiais:
                filiais.append(int(parte))
        return ",".join(map(str, filiais)) or None  # vazio = todas as filiais

    if not valor:
        raise ValueError("valor não pode ser vazio.")
    return valor


# ----------------------------------------------------------------------- listagem
@router.get("", response_model=list[ParametroResponse])
def listar_parametros(db: Session = Depends(get_db), _user=Depends(_ACESSO)):
    parametros = (
        db.query(Parametro)
        .options(joinedload(Parametro.atualizado_por))
        .order_by(Parametro.chave)
        .all()
    )
    return [_to_response(p) for p in parametros]


# ----------------------------------------------------------------------- atualizar
@router.put("/{chave}", response_model=ParametroResponse)
def atualizar_parametro(
    chave: str,
    body: ParametroUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(_ACESSO),
):
    p = db.query(Parametro).filter(Parametro.chave == chave).first()
    if not p:
        raise HTTPException(status_code=404, detail=f"Parâmetro '{chave}' não encontrado.")

    try:
        valor = normalizar_valor(chave, body.valor)
    except ValueError as erro:
        raise HTTPException(status_code=422, detail=str(erro))

    p.valor = valor
    p.id_usuario_atualizacao = current_user.id
    p.atualizado_em = datetime.now(timezone.utc)
    db.commit()
    db.refresh(p)

    return _to_response(p)


# ----------------------------------------------------------------------- pendências
@router.get("/pendencias", response_model=list[PendenciaConfiguracao])
def listar_pendencias(db: Session = Depends(get_db), _user=Depends(get_current_user)):
    """Configurações obrigatórias ainda não preenchidas. Aberto a qualquer
    usuário logado: o alerta aparece para todos, não só para quem configura."""
    pendencias: list[PendenciaConfiguracao] = []

    cnpj = db.query(Parametro.valor).filter(Parametro.chave == CHAVE_CNPJ_DISTRIBUIDOR).scalar()
    if not (cnpj or "").strip():
        pendencias.append(PendenciaConfiguracao(
            chave=CHAVE_CNPJ_DISTRIBUIDOR,
            titulo="CNPJ do distribuidor não configurado",
            mensagem=(
                "Retornos, espelhos, cancelamentos e estoque não são gerados enquanto o CNPJ "
                "do distribuidor não for informado na tela de Parametrização."
            ),
        ))
    return pendencias
