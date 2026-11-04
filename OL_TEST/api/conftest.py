"""
Conftest dos testes de ROTA do OL_API (OL_TEST/api/).

Diferença pro resto do OL_TEST: aqui sobe uma app FastAPI de teste com um
banco SQLite em memória (nunca MySQL/SQL Server de verdade) e um
TestClient. As funções de negócio (app.services.operacoes) são mockadas —
estes testes cobrem a CAMADA DE ROTA (autenticação, status code,
tratamento de erro, rollback de sessão), não a lógica de negócio em si
(já coberta pelos outros arquivos de OL_TEST).
"""
import os
import sys
from datetime import datetime
from pathlib import Path

# O OL_API não é um pacote instalável (é a aplicação), então entra no
# sys.path. O ol_core vem instalado no venv (requirements-test.txt).
OL_API_PATH = Path(__file__).resolve().parent.parent.parent / "OL_API"
if str(OL_API_PATH) not in sys.path:
    sys.path.insert(0, str(OL_API_PATH))

# Valores fake só pra Settings() conseguir instanciar sem depender do .env de
# verdade — nenhum teste aqui conecta em MySQL/SQL Server/FTP de verdade,
# tudo passa por SQLite em memória e mocks.
os.environ.setdefault("MYSQL_HOST", "fake-host")
os.environ.setdefault("MYSQL_PORTA", "3306")
os.environ.setdefault("MYSQL_BANCO", "fake_db")
os.environ.setdefault("MYSQL_USUARIO", "fake_user")
os.environ.setdefault("MYSQL_SENHA", "fake_senha")
os.environ.setdefault("ERP_SERVIDOR", "fake-erp-host")
os.environ.setdefault("ERP_BANCO", "fake_erp_db")
os.environ.setdefault("ERP_USUARIO", "fake_user")
os.environ.setdefault("ERP_SENHA", "fake_senha")
os.environ.setdefault("JWT_SECRET_KEY", "fake-secret-key-somente-para-testes")
os.environ.setdefault("SERVICOS_API_KEY", "fake-servicos-api-key-somente-para-testes")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.security import hash_password, create_access_token
from app.models import Usuario, Perfil, Industria, Pedido


@pytest.fixture(autouse=True)
def _isolar_infra_externa(monkeypatch):
    """Nenhum teste de rota pode chegar no MySQL/ERP de verdade.

    `historico._log` e `titulo_erp.buscar_titulo_erp` relançam ErroConexaoBanco
    (de propósito: o painel precisa avisar que o banco caiu), então sem este
    stub qualquer teste que passe por eles tenta conectar no host fake e falha.
    Testes que precisam de outro comportamento sobrescrevem com monkeypatch."""
    from app.services.operacoes import geracao, historico, titulo_erp

    monkeypatch.setattr(historico, "registrar_historico", lambda *a, **kw: None)
    monkeypatch.setattr(titulo_erp, "verificar_titulo", lambda *a, **kw: [])
    monkeypatch.setattr(geracao, "verificar_titulo", lambda *a, **kw: [])


@pytest.fixture()
def sessao_teste():
    """Banco SQLite em memória, schema recriado do zero a cada teste."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    sessao = SessionLocal()
    try:
        yield sessao
    finally:
        sessao.close()


def _criar_usuario_com_perfil(sessao_teste, nome_perfil: str) -> Usuario:
    perfil = sessao_teste.query(Perfil).filter_by(nome=nome_perfil).first()
    if perfil is None:
        perfil = Perfil(nome=nome_perfil)
        sessao_teste.add(perfil)
        sessao_teste.commit()
        sessao_teste.refresh(perfil)

    usuario = Usuario(
        nome=f"Usuario {nome_perfil}",
        email=f"{nome_perfil.lower().replace(' ', '_')}@teste.com",
        senha_hash=hash_password("senha123"),
        ativo=True,
        id_perfil=perfil.id,
    )
    sessao_teste.add(usuario)
    sessao_teste.commit()
    sessao_teste.refresh(usuario)
    return usuario


def _montar_client(app_router, sessao_teste, nome_perfil: str | None):
    """Monta uma app FastAPI só com o router dado, banco SQLite sobrescrito
    via dependency_overrides, e (opcionalmente) autenticada com um usuário
    do perfil informado. nome_perfil=None devolve um client sem token."""
    from fastapi import FastAPI

    app_teste = FastAPI()
    app_teste.include_router(app_router)
    app_teste.dependency_overrides[get_db] = lambda: sessao_teste

    headers = {}
    if nome_perfil is not None:
        usuario = _criar_usuario_com_perfil(sessao_teste, nome_perfil)
        token = create_access_token(usuario.id)
        headers["Authorization"] = f"Bearer {token}"

    client = TestClient(app_teste, headers=headers)
    return client


@pytest.fixture()
def montar_client(sessao_teste):
    """Fixture-fábrica: montar_client(router, nome_perfil) -> TestClient."""
    def _fabrica(app_router, nome_perfil: str | None = "Operador Logístico"):
        return _montar_client(app_router, sessao_teste, nome_perfil)
    return _fabrica


def criar_pedido_e_industria(sessao_teste, **dados_pedido) -> Pedido:
    """Cria uma Industria + Pedido de teste no banco SQLite em memória."""
    industria = Industria(nome="Industria Teste", cnpj="12345678000199", ativo=True)
    sessao_teste.add(industria)
    sessao_teste.commit()
    sessao_teste.refresh(industria)

    padrao = dict(
        numero_pedido_ol="00000000000000000001",
        id_industria=industria.id,
        nome_arquivo="PEDIDO_TESTE.txt",
        codigo_interno_erp=100,
        cnpj_cliente="12345678000199",
        status_operacional="Verificar",
        criado_em=datetime.now(),
        atualizado_em=datetime.now(),
    )
    padrao.update(dados_pedido)
    pedido = Pedido(**padrao)
    sessao_teste.add(pedido)
    sessao_teste.commit()
    sessao_teste.refresh(pedido)
    return pedido
