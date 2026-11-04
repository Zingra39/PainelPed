"""Testes da rota OL_API/app/routers/servicos.py.

Persiste como teste permanente a validação que foi feita ad-hoc na
correção da task #32 (heartbeat sem autenticação). Banco SQLite em
memória, nenhuma conexão de verdade com MySQL/SQL Server/FTP.
"""
from datetime import datetime, timedelta, timezone

from app.routers import servicos
from app.models import ServicoMonitorado


def _criar_servico(sessao_teste, **dados) -> ServicoMonitorado:
    padrao = dict(
        nome="importa_pedidos",
        ultimo_heartbeat=None,
        status="Nunca executado",
        mensagem=None,
        timeout_minutos=10,
        criado_em=datetime.now(),
        atualizado_em=datetime.now(),
    )
    padrao.update(dados)
    servico = ServicoMonitorado(**padrao)
    sessao_teste.add(servico)
    sessao_teste.commit()
    sessao_teste.refresh(servico)
    return servico


# --------------------------------------------------------------------- heartbeat / autenticação de serviço

def test_heartbeat_sem_chave_retorna_401(sessao_teste, montar_client):
    _criar_servico(sessao_teste)
    client = montar_client(servicos.router, nome_perfil=None)

    resposta = client.post("/servicos/importa_pedidos/heartbeat", json={"status": "OK"})

    assert resposta.status_code == 401


def test_heartbeat_com_chave_errada_retorna_401(sessao_teste, montar_client):
    _criar_servico(sessao_teste)
    client = montar_client(servicos.router, nome_perfil=None)

    resposta = client.post(
        "/servicos/importa_pedidos/heartbeat",
        json={"status": "OK"},
        headers={"X-Service-Key": "chave-forjada-invalida"},
    )

    assert resposta.status_code == 401


def test_heartbeat_com_chave_correta_retorna_204_e_grava_no_banco(sessao_teste, montar_client):
    from app.core.config import settings

    _criar_servico(sessao_teste)
    client = montar_client(servicos.router, nome_perfil=None)

    resposta = client.post(
        "/servicos/importa_pedidos/heartbeat",
        json={"status": "OK", "mensagem": "Teste de validação"},
        headers={"X-Service-Key": settings.servicos_api_key},
    )

    assert resposta.status_code == 204

    sessao_teste.expire_all()
    servico = sessao_teste.query(ServicoMonitorado).filter_by(nome="importa_pedidos").first()
    assert servico.status == "OK"
    assert servico.mensagem == "Teste de validação"


def test_heartbeat_para_servico_inexistente_com_chave_certa_retorna_404(sessao_teste, montar_client):
    from app.core.config import settings

    client = montar_client(servicos.router, nome_perfil=None)

    resposta = client.post(
        "/servicos/servico_fantasma/heartbeat",
        json={"status": "OK"},
        headers={"X-Service-Key": settings.servicos_api_key},
    )

    assert resposta.status_code == 404


# --------------------------------------------------------------------- listar_servicos / executar_servico — continuam exigindo login de Administrador

def test_listar_servicos_sem_token_retorna_401(montar_client):
    client = montar_client(servicos.router, nome_perfil=None)

    resposta = client.get("/servicos")

    assert resposta.status_code == 401


def test_listar_servicos_com_token_de_administrador_retorna_200(sessao_teste, montar_client):
    _criar_servico(sessao_teste)
    client = montar_client(servicos.router, nome_perfil="Administrador")

    resposta = client.get("/servicos")

    assert resposta.status_code == 200
    assert len(resposta.json()) == 1


def test_listar_servicos_com_token_de_perfil_sem_permissao_retorna_403(montar_client):
    client = montar_client(servicos.router, nome_perfil="Operador Logístico")

    resposta = client.get("/servicos")

    assert resposta.status_code == 403


def test_executar_servico_sem_token_retorna_401(montar_client):
    client = montar_client(servicos.router, nome_perfil=None)

    resposta = client.post("/servicos/importa_pedidos/executar")

    assert resposta.status_code == 401


def test_executar_servico_com_nome_nao_permitido_retorna_400(montar_client):
    client = montar_client(servicos.router, nome_perfil="Administrador")

    resposta = client.post("/servicos/script_qualquer_nao_listado/executar")

    assert resposta.status_code == 400
