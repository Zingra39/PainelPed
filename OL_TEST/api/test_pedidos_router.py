"""Testes das rotas de "operações manuais" de OL_API/app/routers/pedidos/:
gerar_retorno, gerar_espelho, reprocessar e registrar_cancelamento.

Banco SQLite em memória (real, não mockado) — as funções de NEGÓCIO
(app.services.operacoes) são mockadas, mas o comportamento de sessão do
SQLAlchemy (commit/rollback) roda de verdade. Isso permite reproduzir o
cenário exato do card #38 (db.commit() sem rollback() prévio mascarando
a exceção original) com uma falha real do SQLAlchemy, não só simulada.
"""
import pytest
from sqlalchemy import text

from app.routers import pedidos
from app.models import Pedido
from ol_core.models.enums.tipo_status_oper import TipoStatusOper
from .conftest import criar_pedido_e_industria


# Cada endpoint de operação manual, com seu path e o atributo mockado em
# app.services.operacoes correspondente — usado pra rodar o mesmo conjunto
# de verificações nos 4 endpoints sem repetir código.
_OPERACOES = [
    ("retorno", "executar_gerar_retorno", "Erro ao gerar retorno"),
    ("espelho", "executar_gerar_espelho", "Erro ao gerar espelho"),
    ("reprocessar", "executar_reprocessar", "Erro ao reprocessar"),
    ("cancelamento", "executar_cancelamento", "Erro ao registrar cancelamento"),
]

# _marcar_falha grava um "Falha no X" especifico pra retorno/espelho/cancelamento
# (mesmo valor que os services automaticos gravam) — reprocessar continua com o
# generico, ja que nao tem coluna propria na tela de Rastreamento.
_STATUS_FALHA_POR_PATH = {
    "retorno": TipoStatusOper.FALHA_RETORNO.value,
    "espelho": TipoStatusOper.FALHA_ESPELHO.value,
    "reprocessar": TipoStatusOper.FALHA.value,
    "cancelamento": TipoStatusOper.FALHA_CANCELAMENTO.value,
}


@pytest.mark.parametrize("path, nome_funcao, mensagem_esperada", _OPERACOES)
def test_endpoint_sem_token_retorna_401(path, nome_funcao, mensagem_esperada, montar_client):
    client = montar_client(pedidos.router, nome_perfil=None)

    resposta = client.post(f"/pedidos/1/{path}")

    assert resposta.status_code == 401


@pytest.mark.parametrize("path, nome_funcao, mensagem_esperada", _OPERACOES)
def test_endpoint_com_perfil_sem_permissao_retorna_403(path, nome_funcao, mensagem_esperada, montar_client):
    # Gerente Comercial existe no sistema (usado em _TODOS), mas não em
    # _OPERACIONAL — não pode disparar operações manuais.
    client = montar_client(pedidos.router, nome_perfil="Gerente Comercial")

    resposta = client.post(f"/pedidos/1/{path}")

    assert resposta.status_code == 403


@pytest.mark.parametrize("path, nome_funcao, mensagem_esperada", _OPERACOES)
def test_endpoint_com_pedido_inexistente_retorna_404(path, nome_funcao, mensagem_esperada, montar_client):
    client = montar_client(pedidos.router, nome_perfil="Operador Logístico")

    resposta = client.post(f"/pedidos/99999/{path}")

    assert resposta.status_code == 404


@pytest.mark.parametrize("path, nome_funcao, mensagem_esperada", _OPERACOES)
def test_endpoint_com_sucesso_retorna_200(path, nome_funcao, mensagem_esperada, sessao_teste, montar_client, monkeypatch):
    from app.services import operacoes

    pedido = criar_pedido_e_industria(sessao_teste)
    monkeypatch.setattr(operacoes, nome_funcao, lambda pedido_db, id_usuario: {"sucesso": True, "mensagem": "ok"})
    client = montar_client(pedidos.router, nome_perfil="Operador Logístico")

    resposta = client.post(f"/pedidos/{pedido.id}/{path}")

    assert resposta.status_code == 200
    assert resposta.json() == {"sucesso": True, "mensagem": "ok"}


@pytest.mark.parametrize("path, nome_funcao, mensagem_esperada", _OPERACOES)
def test_endpoint_com_value_error_retorna_422_e_nao_marca_falha(path, nome_funcao, mensagem_esperada, sessao_teste, montar_client, monkeypatch):
    from app.services import operacoes

    pedido = criar_pedido_e_industria(sessao_teste)

    def levanta_value_error(pedido_db, id_usuario):
        raise ValueError("erro de regra de negócio simulado")

    monkeypatch.setattr(operacoes, nome_funcao, levanta_value_error)
    client = montar_client(pedidos.router, nome_perfil="Operador Logístico")

    resposta = client.post(f"/pedidos/{pedido.id}/{path}")

    assert resposta.status_code == 422
    assert resposta.json()["detail"] == "erro de regra de negócio simulado"

    sessao_teste.expire_all()
    pedido_atualizado = sessao_teste.query(Pedido).filter_by(id=pedido.id).first()
    assert pedido_atualizado.status_operacional == "Verificar"  # não marcado como Falha


@pytest.mark.parametrize("path, nome_funcao, mensagem_esperada", _OPERACOES)
def test_endpoint_com_erro_generico_marca_pedido_como_falha_e_retorna_500(path, nome_funcao, mensagem_esperada, sessao_teste, montar_client, monkeypatch):
    from app.services import operacoes

    pedido = criar_pedido_e_industria(sessao_teste)

    def levanta_erro_generico(pedido_db, id_usuario):
        raise KeyError("erro interno inesperado simulado")

    monkeypatch.setattr(operacoes, nome_funcao, levanta_erro_generico)
    client = montar_client(pedidos.router, nome_perfil="Operador Logístico")

    resposta = client.post(f"/pedidos/{pedido.id}/{path}")

    assert resposta.status_code == 500
    assert resposta.json()["detail"] == mensagem_esperada

    sessao_teste.expire_all()
    pedido_atualizado = sessao_teste.query(Pedido).filter_by(id=pedido.id).first()
    assert pedido_atualizado.status_operacional == _STATUS_FALHA_POR_PATH[path]


# --------------------------------------------------------------------- regressão do card #38 (db.commit() sem rollback() prévio)

@pytest.mark.parametrize("path, nome_funcao, mensagem_esperada", _OPERACOES)
def test_endpoint_com_erro_real_do_sqlalchemy_ainda_retorna_500_com_a_mensagem_certa(path, nome_funcao, mensagem_esperada, sessao_teste, montar_client, monkeypatch):
    """Regressão do card #38: se o erro original já vem do próprio
    SQLAlchemy — aqui, uma IntegrityError real de violação de UNIQUE,
    disparada durante um flush, não simulada — a sessão fica em estado
    de rollback Verificar. Sem o db.rollback() dentro de _marcar_falha, o
    commit() interno estoura um SEGUNDO erro (PendingRollbackError) que
    mascara o 500 esperado.

    IMPORTANTE: um erro de SELECT (ex.: "SELECT * FROM tabela_inexistente")
    NÃO reproduz esse cenário — no SQLAlchemy 2.0, uma falha de leitura
    fora de um flush não deixa a sessão suja, só uma falha durante
    flush/commit (INSERT/UPDATE/DELETE) deixa. Por isso o teste provoca
    a falha real com um INSERT duplicado (numero_pedido_ol é UNIQUE),
    confirmado isoladamente antes desta correção."""
    from app.services import operacoes

    pedido = criar_pedido_e_industria(sessao_teste)

    def levanta_erro_real_do_sqlalchemy(pedido_db, id_usuario):
        duplicado = Pedido(
            numero_pedido_ol=pedido_db.numero_pedido_ol,
            id_industria=pedido_db.id_industria,
            status_operacional="Verificar",
        )
        sessao_teste.add(duplicado)
        sessao_teste.commit()
        return {}

    monkeypatch.setattr(operacoes, nome_funcao, levanta_erro_real_do_sqlalchemy)
    client = montar_client(pedidos.router, nome_perfil="Operador Logístico")

    resposta = client.post(f"/pedidos/{pedido.id}/{path}")

    assert resposta.status_code == 500
    assert resposta.json()["detail"] == mensagem_esperada

    sessao_teste.expire_all()
    pedido_atualizado = sessao_teste.query(Pedido).filter_by(id=pedido.id).first()
    assert pedido_atualizado.status_operacional == _STATUS_FALHA_POR_PATH[path]


# --------------------------------------------------------------------- transmitir individual (/{id}/transmitir)
# Endpoint separado dos demais em _OPERACOES porque tem uma pré-condição própria
# (status_erp == 'Não Transmitido') e transições de status próprias
# (Transmitindo -> Transmitido/Falha, replicando o loop de /lote/transmitir).

def _criar_pedido_nao_transmitido(sessao_teste, **dados_pedido):
    dados_pedido.setdefault("status_erp", "Não Transmitido")
    return criar_pedido_e_industria(sessao_teste, **dados_pedido)


def test_transmitir_sem_token_retorna_401(montar_client):
    client = montar_client(pedidos.router, nome_perfil=None)

    resposta = client.post("/pedidos/1/transmitir")

    assert resposta.status_code == 401


def test_transmitir_com_perfil_sem_permissao_retorna_403(montar_client):
    client = montar_client(pedidos.router, nome_perfil="Gerente Comercial")

    resposta = client.post("/pedidos/1/transmitir")

    assert resposta.status_code == 403


def test_transmitir_com_pedido_inexistente_retorna_404(montar_client):
    client = montar_client(pedidos.router, nome_perfil="Operador Logístico")

    resposta = client.post("/pedidos/99999/transmitir")

    assert resposta.status_code == 404


def test_transmitir_com_pedido_ja_transmitido_retorna_422_sem_chamar_operacao(sessao_teste, montar_client, monkeypatch):
    from app.services import operacoes

    pedido = criar_pedido_e_industria(sessao_teste, status_erp="Transmitido")
    chamou = []
    monkeypatch.setattr(operacoes, "executar_transmitir", lambda pedido_db, id_usuario: chamou.append(True))
    client = montar_client(pedidos.router, nome_perfil="Operador Logístico")

    resposta = client.post(f"/pedidos/{pedido.id}/transmitir")

    assert resposta.status_code == 422
    assert "já foi transmitido" in resposta.json()["detail"]
    assert chamou == []


def test_transmitir_com_sucesso_retorna_200_e_marca_transmitido(sessao_teste, montar_client, monkeypatch):
    from app.services import operacoes

    pedido = _criar_pedido_nao_transmitido(sessao_teste)
    monkeypatch.setattr(operacoes, "executar_transmitir", lambda pedido_db, id_usuario: {"sucesso": True, "mensagem": "ok"})
    client = montar_client(pedidos.router, nome_perfil="Operador Logístico")

    resposta = client.post(f"/pedidos/{pedido.id}/transmitir")

    assert resposta.status_code == 200
    assert resposta.json() == {"sucesso": True, "mensagem": "ok"}

    sessao_teste.expire_all()
    pedido_atualizado = sessao_teste.query(Pedido).filter_by(id=pedido.id).first()
    assert pedido_atualizado.status_operacional == "Transmitido"
    assert pedido_atualizado.status_erp == "Transmitido"


def test_transmitir_com_value_error_retorna_422_e_nao_marca_falha(sessao_teste, montar_client, monkeypatch):
    from app.services import operacoes

    pedido = _criar_pedido_nao_transmitido(sessao_teste)

    def levanta_value_error(pedido_db, id_usuario):
        raise ValueError("arquivo não encontrado na pasta de backup")

    monkeypatch.setattr(operacoes, "executar_transmitir", levanta_value_error)
    client = montar_client(pedidos.router, nome_perfil="Operador Logístico")

    resposta = client.post(f"/pedidos/{pedido.id}/transmitir")

    assert resposta.status_code == 422
    assert resposta.json()["detail"] == "arquivo não encontrado na pasta de backup"

    sessao_teste.expire_all()
    pedido_atualizado = sessao_teste.query(Pedido).filter_by(id=pedido.id).first()
    assert pedido_atualizado.status_operacional != "Falha"


def test_transmitir_com_erro_generico_marca_pedido_como_falha_e_retorna_500(sessao_teste, montar_client, monkeypatch):
    from app.services import operacoes

    pedido = _criar_pedido_nao_transmitido(sessao_teste)

    def levanta_erro_generico(pedido_db, id_usuario):
        raise KeyError("erro interno inesperado simulado")

    monkeypatch.setattr(operacoes, "executar_transmitir", levanta_erro_generico)
    client = montar_client(pedidos.router, nome_perfil="Operador Logístico")

    resposta = client.post(f"/pedidos/{pedido.id}/transmitir")

    assert resposta.status_code == 500
    assert resposta.json()["detail"] == "Erro ao transmitir"

    sessao_teste.expire_all()
    pedido_atualizado = sessao_teste.query(Pedido).filter_by(id=pedido.id).first()
    assert pedido_atualizado.status_operacional == "Falha"
