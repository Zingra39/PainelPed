import unicodedata
from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session, joinedload

from ol_core.core.logger import logger

from app.core.config import settings
from app.core.database import get_db
from app.core.security import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    from app.models import Usuario

    payload = decode_token(token, "access")
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido ou expirado.")

    user = (
        db.query(Usuario)
        .options(joinedload(Usuario.perfil))
        .filter(Usuario.id == int(payload["sub"]), Usuario.ativo == True)
        .first()
    )
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário não encontrado.")
    return user


# --------------------------------------------------------------- perfis
#
# A autorização compara o nome do perfil gravado em `perfil.nome` com os
# literais passados em require_perfis(...). Comparar string crua se mostrou
# frágil: o perfil "Operador Logístico" ficou gravado como "Operador
# Log?stico" (um cliente MySQL com charset errado converte o "í" em "?"), e
# TODOS os endpoints passaram a devolver 403 para esse perfil — sem nenhuma
# pista no log, porque o 403 era silencioso.
#
# Agora a comparação é tolerante a variação de escrita que não muda o
# significado do perfil (acento, caixa, espaço extra) e a caractere destruído
# por conversão de charset, e toda negativa é registrada em log com o valor
# exato recebido do banco.

# Caracteres que sobram quando uma letra não pôde ser representada no charset
# de origem: "?" (substituição do MySQL) e U+FFFD (replacement char do Unicode).
_MARCAS_DANO_CHARSET = frozenset({"?", "�"})

# Quantos caracteres danificados um nome pode ter e ainda ser reconhecido.
# Nomes reais de perfil têm um ou dois acentos ("Operador Logístico",
# "Supervisão Comercial"); o teto impede que um nome formado só por "?" case
# com qualquer perfil de mesmo tamanho.
_MAX_CARACTERES_DANIFICADOS = 3


def _normalizar_perfil(nome: Optional[str]) -> str:
    """Reduz o nome do perfil à sua forma comparável: sem acento, minúsculo e
    com os espaços colapsados. "Operador Logístico" e " operador  LOGISTICO "
    viram a mesma coisa."""
    if not nome:
        return ""
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFKD", nome) if not unicodedata.combining(c)
    )
    return " ".join(sem_acento.casefold().split())


def _perfil_equivalente(recebido: Optional[str], esperado: str) -> bool:
    """True se o nome recebido do banco designa o mesmo perfil que o esperado.

    Além da comparação normalizada, aceita nomes em que caracteres foram
    destruídos por conversão de charset: cada "?"/U+FFFD vale por exatamente um
    caractere na mesma posição. É deliberadamente estreito — exige mesmo
    comprimento, todos os outros caracteres idênticos e no máximo
    _MAX_CARACTERES_DANIFICADOS posições danificadas (sempre minoria do nome) —,
    então "Operador Log?stico" casa com "Operador Logístico", mas
    "Administrador" nunca casa com "Gerente Comercial" e um nome só de "?" não
    casa com nada."""
    alvo = _normalizar_perfil(esperado)
    atual = _normalizar_perfil(recebido)

    if atual == alvo:
        return True
    if len(atual) != len(alvo):
        return False

    danificados = sum(1 for c in atual if c in _MARCAS_DANO_CHARSET)
    if danificados == 0 or danificados > _MAX_CARACTERES_DANIFICADOS:
        return False
    # O dano tem de ser minoria do nome: o resto precisa identificar o perfil.
    if danificados * 2 >= len(alvo):
        return False
    return all(a == b or a in _MARCAS_DANO_CHARSET for a, b in zip(atual, alvo))


def require_perfis(*allowed: str):
    def dependency(current_user=Depends(get_current_user)):
        nome = current_user.perfil.nome if current_user.perfil else None

        if any(_perfil_equivalente(nome, permitido) for permitido in allowed):
            return current_user

        # ascii() em vez de repr(): deixa o valor legível como \xed / � em
        # qualquer console ou arquivo de log, seja qual for o encoding dele —
        # que é exatamente o tipo de problema que costuma cair aqui.
        logger.warning(
            f"Acesso negado (403) para usuario id={current_user.id} "
            f"({current_user.email}): perfil gravado no banco = {ascii(nome)}, "
            f"perfis aceitos = {ascii(list(allowed))}. Se o nome parece certo na "
            f"tela mas nao casa aqui, conferir dano de charset em `perfil.nome`."
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Acesso negado. Perfil necessário: {', '.join(allowed)}.",
        )

    return dependency


# Todos os perfis que o código conhece. Mantido aqui, num só lugar, para a
# checagem de inicialização (main.py) poder conferir o banco contra o código.
# Os routers ainda declaram seus próprios subconjuntos em require_perfis(...).
PERFIS_CONHECIDOS = ["Administrador", "Operador Logístico", "Gerente Comercial"]


def perfis_ausentes_no_banco(db: Session, esperados: Optional[list[str]] = None) -> list[str]:
    """Devolve a lista de perfis esperados que NÃO foram encontrados na tabela
    `perfil` (comparando com a mesma tolerância usada na autorização).

    Usada na checagem de inicialização da API (main.py): se um perfil esperado
    pelo código não existe no banco, todo usuário que deveria tê-lo fica
    trancado fora do sistema — melhor gritar no boot do que descobrir por 403
    silencioso em produção."""
    from app.models import Perfil

    esperados = esperados if esperados is not None else PERFIS_CONHECIDOS
    nomes = [p.nome for p in db.query(Perfil).all()]
    return [
        esperado
        for esperado in esperados
        if not any(_perfil_equivalente(nome, esperado) for nome in nomes)
    ]


def require_service_key(x_service_key: str = Header(default=None, alias="X-Service-Key")):
    """
    Autenticação para chamadas serviço-a-serviço (ex.: heartbeat do OL_Services).
    Não usa login de operador — compara uma chave compartilhada enviada no header
    'X-Service-Key' com SERVICOS_API_KEY. Se a chave não estiver configurada no
    servidor, o acesso fica sempre negado (fail-closed), em vez de aberto.
    """
    chave_configurada = settings.servicos_api_key
    if not chave_configurada or not x_service_key or x_service_key != chave_configurada:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Chave de serviço inválida ou ausente.",
        )
