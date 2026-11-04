"""Testes da feature "Em Analise" (OL_API/app/routers/pedidos/).

Um operador marca o pedido da triagem como "Em Analise" para os demais saberem
quem está cuidando dele e ninguém o transmitir por acidente. O que estes testes
travam:

- POST   /pedidos/{id}/analise  -> inicia (só Pronto/Verificar, ainda na
  triagem; 409 se outro operador chegou primeiro);
- DELETE /pedidos/{id}/analise  -> encerra: reprocessa e devolve Pronto ou
  Verificar; só o autor ou um Administrador; se o reprocessamento falhar o
  pedido VOLTA para "Em Analise" (nunca fica preso em "Reprocessando");
- guardas: pedido em análise não é transmitido nem reprocessado (individual e
  em lote);
- os campos de autoria (em_analise_por etc.) chegam nas respostas de listagem e
  detalhe só enquanto o pedido está em análise.

Mesma infra de test_pedidos_router.py: SQLite em memória real, funções de
NEGÓCIO (app.services.operacoes) mockadas. Aqui o "reprocessamento" falso grava
o status na mesma sessão, imitando o que o ol_core grava por conexão própria.
"""
from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.core.security import create_access_token, hash_password
from app.models import Pedido, Perfil, Usuario
from app.routers import pedidos
from app.routers.pedidos._comum import _marcar_transmitindo
from app.routers.pedidos.lote import _transmitir_pedido
from app.services import operacoes
from ol_core.models.enums.tipo_status_oper import TipoStatusOper
from .conftest import criar_pedido_e_industria

EM_ANALISE = TipoStatusOper.EM_ANALISE.value
NAO_TRANSMITIDO = "Não Transmitido"


# ----------------------------------------------------------------------- infra

def _cliente(sessao_teste, nome_perfil: str, email: str):
    """TestClient autenticado como um usuário NOVO do perfil dado.

    O `montar_client` do conftest cria o e-mail a partir do perfil, então dois
    operadores no mesmo teste (o autor da análise e "outro operador") colidiriam
    no UNIQUE do e-mail. Aqui o e-mail é escolhido pelo teste."""
    perfil = sessao_teste.query(Perfil).filter_by(nome=nome_perfil).first()
    if perfil is None:
        perfil = Perfil(nome=nome_perfil)
        sessao_teste.add(perfil)
        sessao_teste.commit()
        sessao_teste.refresh(perfil)

    usuario = Usuario(
        nome=f"{nome_perfil} {email.split('@')[0]}",
        email=email,
        senha_hash=hash_password("senha123"),
        ativo=True,
        id_perfil=perfil.id,
    )
    sessao_teste.add(usuario)
    sessao_teste.commit()
    sessao_teste.refresh(usuario)

    app_teste = FastAPI()
    app_teste.include_router(pedidos.router)
    app_teste.dependency_overrides[get_db] = lambda: sessao_teste
    client = TestClient(
        app_teste, headers={"Authorization": f"Bearer {create_access_token(usuario.id)}"}
    )
    return client, usuario


def _pedido_triagem(sessao_teste, **dados) -> Pedido:
    """Pedido na triagem (Não Transmitido) e Pronto — o caso comum para entrar em análise."""
    dados.setdefault("status_erp", NAO_TRANSMITIDO)
    dados.setdefault("status_operacional", TipoStatusOper.PRONTO.value)
    return criar_pedido_e_industria(sessao_teste, **dados)


def _outro_pedido(sessao_teste, base: Pedido, numero: str, **dados) -> Pedido:
    """Segundo pedido na mesma indústria (criar_pedido_e_industria cria uma
    Industria nova a cada chamada, e o CNPJ dela é UNIQUE)."""
    padrao = dict(
        numero_pedido_ol=numero,
        id_industria=base.id_industria,
        nome_arquivo=f"PEDIDO_{numero}.txt",
        cnpj_cliente="12345678000199",
        status_erp=NAO_TRANSMITIDO,
        status_operacional=TipoStatusOper.PRONTO.value,
        criado_em=datetime.now(),
        atualizado_em=datetime.now(),
    )
    padrao.update(dados)
    pedido = Pedido(**padrao)
    sessao_teste.add(pedido)
    sessao_teste.commit()
    sessao_teste.refresh(pedido)
    return pedido


def _recarregar(sessao_teste, pedido: Pedido) -> Pedido:
    sessao_teste.expire_all()
    return sessao_teste.query(Pedido).filter_by(id=pedido.id).first()


def _em_analise_por(sessao_teste, pedido: Pedido, usuario: Usuario) -> Pedido:
    """Põe o pedido em análise diretamente no banco (estado pré-existente do teste)."""
    pedido.status_operacional = EM_ANALISE
    pedido.id_usuario_analise = usuario.id
    pedido.em_analise_desde = datetime.now()
    sessao_teste.commit()
    return _recarregar(sessao_teste, pedido)


@pytest.fixture()
def logs(monkeypatch):
    """Captura o histórico gravado (que em produção vai para o MySQL por
    conexão própria do ol_core) em vez de tentar conectar."""
    registrados: list[tuple] = []
    monkeypatch.setattr(
        operacoes, "registrar_log_analise",
        lambda numero, acao, detalhe, id_usuario: registrados.append((numero, acao, detalhe, id_usuario)),
    )
    return registrados


def _reprocessar_falso(sessao_teste, status_final, sucesso=True, mensagem="Reprocessamento concluído."):
    """Imita executar_reprocessar: grava o status final no banco (como o ol_core
    faz) e devolve o dict de resultado. Registra as chamadas em `.chamadas`."""
    chamadas: list[int] = []

    def _fn(pedido_db, id_usuario):
        chamadas.append(pedido_db.id)
        sessao_teste.query(Pedido).filter(Pedido.id == pedido_db.id).update(
            {"status_operacional": status_final}, synchronize_session=False
        )
        sessao_teste.commit()
        return {"sucesso": sucesso, "mensagem": mensagem}

    _fn.chamadas = chamadas
    return _fn


def test_valor_do_status_em_analise_nao_tem_acento():
    # Igual aos demais valores de TipoStatusOper: sem acento por causa do
    # histórico de dano de charset em produção. Mudar isto quebra o que já está
    # gravado no banco e o filtro da tela de Triagem.
    assert EM_ANALISE == "Em Analise"


# ------------------------------------------------------------- iniciar (POST)

def test_iniciar_sem_token_retorna_401(montar_client):
    client = montar_client(pedidos.router, nome_perfil=None)

    assert client.post("/pedidos/1/analise").status_code == 401


def test_iniciar_com_perfil_sem_permissao_retorna_403(montar_client):
    # Gerente Comercial só consulta: análise é ação operacional.
    client = montar_client(pedidos.router, nome_perfil="Gerente Comercial")

    assert client.post("/pedidos/1/analise").status_code == 403


def test_iniciar_com_pedido_inexistente_retorna_404(montar_client):
    client = montar_client(pedidos.router, nome_perfil="Operador Logístico")

    assert client.post("/pedidos/99999/analise").status_code == 404


@pytest.mark.parametrize("status_inicial", [TipoStatusOper.PRONTO.value, TipoStatusOper.VERIFICAR.value])
def test_iniciar_marca_pedido_em_analise_pelo_usuario_logado(sessao_teste, logs, status_inicial):
    pedido = _pedido_triagem(sessao_teste, status_operacional=status_inicial)
    client, usuario = _cliente(sessao_teste, "Operador Logístico", "ana@teste.com")

    resposta = client.post(f"/pedidos/{pedido.id}/analise")

    assert resposta.status_code == 200
    assert resposta.json()["sucesso"] is True
    atual = _recarregar(sessao_teste, pedido)
    assert atual.status_operacional == EM_ANALISE
    assert atual.id_usuario_analise == usuario.id
    assert atual.em_analise_desde is not None
    assert [(acao, uid) for _n, acao, _d, uid in logs] == [("Análise iniciada", usuario.id)]


@pytest.mark.parametrize("status_invalido", [
    "Importado",
    TipoStatusOper.TRANSMITINDO.value,
    TipoStatusOper.REPROCESSANDO.value,
    TipoStatusOper.FALHA.value,
])
def test_iniciar_so_aceita_pronto_ou_verificar(sessao_teste, logs, status_invalido):
    pedido = _pedido_triagem(sessao_teste, status_operacional=status_invalido)
    client, _ = _cliente(sessao_teste, "Operador Logístico", "ana@teste.com")

    resposta = client.post(f"/pedidos/{pedido.id}/analise")

    assert resposta.status_code == 422
    assert "Pronto ou Verificar" in resposta.json()["detail"]
    atual = _recarregar(sessao_teste, pedido)
    assert atual.status_operacional == status_invalido
    assert atual.id_usuario_analise is None
    assert logs == []


def test_iniciar_recusa_pedido_que_ja_saiu_da_triagem(sessao_teste, logs):
    pedido = _pedido_triagem(sessao_teste, status_erp="Transmitido")
    client, _ = _cliente(sessao_teste, "Operador Logístico", "ana@teste.com")

    resposta = client.post(f"/pedidos/{pedido.id}/analise")

    assert resposta.status_code == 422
    assert "triagem" in resposta.json()["detail"]
    assert _recarregar(sessao_teste, pedido).status_operacional == TipoStatusOper.PRONTO.value
    assert logs == []


def test_iniciar_quando_outro_operador_ja_esta_analisando_retorna_409_e_preserva_o_dono(sessao_teste, logs):
    pedido = _pedido_triagem(sessao_teste)
    _, ana = _cliente(sessao_teste, "Operador Logístico", "ana@teste.com")
    bruno_client, _ = _cliente(sessao_teste, "Operador Logístico", "bruno@teste.com")
    _em_analise_por(sessao_teste, pedido, ana)

    resposta = bruno_client.post(f"/pedidos/{pedido.id}/analise")

    assert resposta.status_code == 409
    assert ana.nome in resposta.json()["detail"]
    atual = _recarregar(sessao_teste, pedido)
    assert atual.id_usuario_analise == ana.id  # quem chegou primeiro continua dono
    assert logs == []


def test_iniciar_duas_vezes_pelo_mesmo_usuario_tambem_retorna_409(sessao_teste, logs):
    pedido = _pedido_triagem(sessao_teste)
    client, _ = _cliente(sessao_teste, "Operador Logístico", "ana@teste.com")

    primeira = client.post(f"/pedidos/{pedido.id}/analise")
    segunda = client.post(f"/pedidos/{pedido.id}/analise")

    assert primeira.status_code == 200
    assert segunda.status_code == 409
    assert len(logs) == 1  # só a primeira marcação entra no histórico


# ------------------------------------------------------------ encerrar (DELETE)

def test_encerrar_sem_token_retorna_401(montar_client):
    client = montar_client(pedidos.router, nome_perfil=None)

    assert client.delete("/pedidos/1/analise").status_code == 401


def test_encerrar_com_perfil_sem_permissao_retorna_403(montar_client):
    client = montar_client(pedidos.router, nome_perfil="Gerente Comercial")

    assert client.delete("/pedidos/1/analise").status_code == 403


def test_encerrar_com_pedido_inexistente_retorna_404(montar_client):
    client = montar_client(pedidos.router, nome_perfil="Operador Logístico")

    assert client.delete("/pedidos/99999/analise").status_code == 404


def test_encerrar_pedido_que_nao_esta_em_analise_retorna_422_sem_reprocessar(sessao_teste, logs, monkeypatch):
    pedido = _pedido_triagem(sessao_teste)
    client, _ = _cliente(sessao_teste, "Operador Logístico", "ana@teste.com")
    falso = _reprocessar_falso(sessao_teste, TipoStatusOper.PRONTO.value)
    monkeypatch.setattr(operacoes, "executar_reprocessar", falso)

    resposta = client.delete(f"/pedidos/{pedido.id}/analise")

    assert resposta.status_code == 422
    assert "não está em análise" in resposta.json()["detail"]
    assert falso.chamadas == []


def test_encerrar_por_outro_operador_retorna_403_e_nao_mexe_no_pedido(sessao_teste, logs, monkeypatch):
    pedido = _pedido_triagem(sessao_teste)
    _, ana = _cliente(sessao_teste, "Operador Logístico", "ana@teste.com")
    bruno_client, _ = _cliente(sessao_teste, "Operador Logístico", "bruno@teste.com")
    _em_analise_por(sessao_teste, pedido, ana)
    falso = _reprocessar_falso(sessao_teste, TipoStatusOper.PRONTO.value)
    monkeypatch.setattr(operacoes, "executar_reprocessar", falso)

    resposta = bruno_client.delete(f"/pedidos/{pedido.id}/analise")

    assert resposta.status_code == 403
    assert ana.nome in resposta.json()["detail"]
    atual = _recarregar(sessao_teste, pedido)
    assert atual.status_operacional == EM_ANALISE
    assert atual.id_usuario_analise == ana.id
    assert falso.chamadas == []


def test_encerrar_pelo_autor_reprocessa_e_devolve_pronto(sessao_teste, logs, monkeypatch):
    pedido = _pedido_triagem(sessao_teste)
    client, ana = _cliente(sessao_teste, "Operador Logístico", "ana@teste.com")
    _em_analise_por(sessao_teste, pedido, ana)
    falso = _reprocessar_falso(sessao_teste, TipoStatusOper.PRONTO.value)
    monkeypatch.setattr(operacoes, "executar_reprocessar", falso)

    resposta = client.delete(f"/pedidos/{pedido.id}/analise")

    assert resposta.status_code == 200
    assert resposta.json()["sucesso"] is True
    assert "Pronto" in resposta.json()["mensagem"]
    assert falso.chamadas == [pedido.id]  # reprocessou exatamente uma vez
    atual = _recarregar(sessao_teste, pedido)
    assert atual.status_operacional == TipoStatusOper.PRONTO.value
    assert atual.id_usuario_analise is None
    assert atual.em_analise_desde is None
    assert [acao for _n, acao, _d, _u in logs] == ["Análise encerrada"]


def test_encerrar_com_ocorrencias_devolve_verificar_e_ainda_assim_encerra_a_analise(sessao_teste, logs, monkeypatch):
    # O reprocessamento acha pendências: LayouFactory.reprocessar devolve
    # sucesso=False, mas isso é um resultado válido da análise — a análise
    # termina e o pedido volta como Verificar.
    pedido = _pedido_triagem(sessao_teste, status_operacional=TipoStatusOper.VERIFICAR.value)
    client, ana = _cliente(sessao_teste, "Operador Logístico", "ana@teste.com")
    _em_analise_por(sessao_teste, pedido, ana)
    falso = _reprocessar_falso(
        sessao_teste, TipoStatusOper.VERIFICAR.value, sucesso=False,
        mensagem="Reprocessamento concluído com 2 ocorrência(s) pendente(s).",
    )
    monkeypatch.setattr(operacoes, "executar_reprocessar", falso)

    resposta = client.delete(f"/pedidos/{pedido.id}/analise")

    assert resposta.status_code == 200
    assert "Verificar" in resposta.json()["mensagem"]
    atual = _recarregar(sessao_teste, pedido)
    assert atual.status_operacional == TipoStatusOper.VERIFICAR.value
    assert atual.id_usuario_analise is None
    assert atual.em_analise_desde is None


def test_administrador_pode_encerrar_analise_de_outro_usuario(sessao_teste, logs, monkeypatch):
    # Destrava o pedido deixado em análise por quem saiu sem encerrar.
    pedido = _pedido_triagem(sessao_teste)
    _, ana = _cliente(sessao_teste, "Operador Logístico", "ana@teste.com")
    admin_client, admin = _cliente(sessao_teste, "Administrador", "admin@teste.com")
    _em_analise_por(sessao_teste, pedido, ana)
    monkeypatch.setattr(operacoes, "executar_reprocessar", _reprocessar_falso(sessao_teste, TipoStatusOper.PRONTO.value))

    resposta = admin_client.delete(f"/pedidos/{pedido.id}/analise")

    assert resposta.status_code == 200
    atual = _recarregar(sessao_teste, pedido)
    assert atual.status_operacional == TipoStatusOper.PRONTO.value
    assert atual.id_usuario_analise is None
    assert logs[-1][1:] == ("Análise encerrada", logs[-1][2], admin.id)  # quem encerrou foi o admin


def test_encerrar_com_erro_de_regra_volta_para_em_analise_e_preserva_o_autor(sessao_teste, logs, monkeypatch):
    # Caso real: o arquivo de backup do pedido não existe. executar_reprocessar
    # levanta ValueError DEPOIS de já ter gravado "Reprocessando" — sem o
    # tratamento do encerramento o pedido ficaria preso nesse status.
    pedido = _pedido_triagem(sessao_teste)
    client, ana = _cliente(sessao_teste, "Operador Logístico", "ana@teste.com")
    original = _em_analise_por(sessao_teste, pedido, ana)
    desde = original.em_analise_desde

    def levanta(pedido_db, id_usuario):
        raise ValueError("Arquivo 'X.txt' não encontrado na pasta de backup.")

    monkeypatch.setattr(operacoes, "executar_reprocessar", levanta)

    resposta = client.delete(f"/pedidos/{pedido.id}/analise")

    assert resposta.status_code == 422
    assert "não encontrado na pasta de backup" in resposta.json()["detail"]
    assert "continua em análise" in resposta.json()["detail"]
    atual = _recarregar(sessao_teste, pedido)
    assert atual.status_operacional == EM_ANALISE          # nunca "Reprocessando"
    assert atual.id_usuario_analise == ana.id              # autor preservado
    assert atual.em_analise_desde == desde                 # data original preservada
    assert [acao for _n, acao, _d, _u in logs] == ["Falha ao encerrar análise"]


def test_encerrar_com_erro_inesperado_retorna_500_e_mantem_em_analise_sem_marcar_falha(sessao_teste, logs, monkeypatch):
    pedido = _pedido_triagem(sessao_teste)
    client, ana = _cliente(sessao_teste, "Operador Logístico", "ana@teste.com")
    _em_analise_por(sessao_teste, pedido, ana)

    def levanta(pedido_db, id_usuario):
        raise KeyError("erro interno inesperado simulado")

    monkeypatch.setattr(operacoes, "executar_reprocessar", levanta)

    resposta = client.delete(f"/pedidos/{pedido.id}/analise")

    assert resposta.status_code == 500
    atual = _recarregar(sessao_teste, pedido)
    assert atual.status_operacional == EM_ANALISE  # não vira "Falha": o pedido segue em análise
    assert atual.id_usuario_analise == ana.id


def test_encerrar_quando_reprocessamento_falha_em_silencio_volta_para_em_analise(sessao_teste, logs, monkeypatch):
    # LayouFactory.reprocessar captura as próprias exceções e devolve
    # (False, "Erro ...") SEM tocar no status — o pedido ficaria em
    # "Reprocessando". O encerramento decide pelo status gravado no banco, não
    # pelo flag de sucesso, e por isso restaura a análise.
    pedido = _pedido_triagem(sessao_teste)
    client, ana = _cliente(sessao_teste, "Operador Logístico", "ana@teste.com")
    _em_analise_por(sessao_teste, pedido, ana)
    chamadas: list[int] = []

    def falha_silenciosa(pedido_db, id_usuario):
        chamadas.append(pedido_db.id)
        return {"sucesso": False, "mensagem": "Erro ao reprocessar arquivo X para objeto Pedido."}

    monkeypatch.setattr(operacoes, "executar_reprocessar", falha_silenciosa)

    resposta = client.delete(f"/pedidos/{pedido.id}/analise")

    assert resposta.status_code == 422
    assert "Erro ao reprocessar arquivo" in resposta.json()["detail"]
    assert chamadas == [pedido.id]
    atual = _recarregar(sessao_teste, pedido)
    assert atual.status_operacional == EM_ANALISE
    assert atual.id_usuario_analise == ana.id


# ----------------------------------------------- guardas: transmitir/reprocessar

def test_transmitir_individual_recusa_pedido_em_analise(sessao_teste, logs, monkeypatch):
    pedido = _pedido_triagem(sessao_teste)
    client, ana = _cliente(sessao_teste, "Operador Logístico", "ana@teste.com")
    _em_analise_por(sessao_teste, pedido, ana)
    chamou: list[bool] = []
    monkeypatch.setattr(operacoes, "executar_transmitir", lambda p, u: chamou.append(True))

    resposta = client.post(f"/pedidos/{pedido.id}/transmitir")

    assert resposta.status_code == 422
    assert "em análise" in resposta.json()["detail"]
    assert ana.nome in resposta.json()["detail"]
    assert chamou == []
    atual = _recarregar(sessao_teste, pedido)
    assert atual.status_operacional == EM_ANALISE  # não foi para Transmitindo nem Falha


def test_transmitir_individual_depois_de_encerrar_a_analise_funciona(sessao_teste, logs, monkeypatch):
    pedido = _pedido_triagem(sessao_teste)
    client, ana = _cliente(sessao_teste, "Operador Logístico", "ana@teste.com")
    _em_analise_por(sessao_teste, pedido, ana)
    monkeypatch.setattr(operacoes, "executar_reprocessar", _reprocessar_falso(sessao_teste, TipoStatusOper.PRONTO.value))
    monkeypatch.setattr(operacoes, "executar_transmitir", lambda p, u: {"sucesso": True, "mensagem": "ok"})

    assert client.delete(f"/pedidos/{pedido.id}/analise").status_code == 200
    resposta = client.post(f"/pedidos/{pedido.id}/transmitir")

    assert resposta.status_code == 200
    assert _recarregar(sessao_teste, pedido).status_operacional == TipoStatusOper.TRANSMITIDO.value


def test_reprocessar_individual_recusa_pedido_em_analise(sessao_teste, logs, monkeypatch):
    pedido = _pedido_triagem(sessao_teste)
    client, ana = _cliente(sessao_teste, "Operador Logístico", "ana@teste.com")
    _em_analise_por(sessao_teste, pedido, ana)
    falso = _reprocessar_falso(sessao_teste, TipoStatusOper.PRONTO.value)
    monkeypatch.setattr(operacoes, "executar_reprocessar", falso)

    resposta = client.post(f"/pedidos/{pedido.id}/reprocessar")

    assert resposta.status_code == 422
    assert "em análise" in resposta.json()["detail"]
    assert falso.chamadas == []
    assert _recarregar(sessao_teste, pedido).status_operacional == EM_ANALISE


def test_lote_transmitir_ignora_pedido_em_analise(sessao_teste, logs, monkeypatch):
    livre = _pedido_triagem(sessao_teste, numero_pedido_ol="00000000000000000001")
    _, ana = _cliente(sessao_teste, "Operador Logístico", "ana@teste.com")
    analisado = _em_analise_por(
        sessao_teste, _outro_pedido(sessao_teste, livre, "00000000000000000002"), ana
    )
    client, _ = _cliente(sessao_teste, "Operador Logístico", "bruno@teste.com")
    transmitidos: list[str] = []

    def transmite(pedido_db, id_usuario):
        transmitidos.append(pedido_db.numero_pedido_ol)
        return {"sucesso": True, "mensagem": "ok"}

    monkeypatch.setattr(operacoes, "executar_transmitir", transmite)

    resposta = client.post("/pedidos/lote/transmitir", json={"apenas_sem_ocorrencia": False})

    assert resposta.status_code == 200
    assert resposta.json()["total"] == 1
    assert transmitidos == ["00000000000000000001"]
    assert _recarregar(sessao_teste, analisado).status_operacional == EM_ANALISE


def test_preview_lote_transmitir_nao_conta_pedido_em_analise(sessao_teste, logs):
    # O preview e a execução usam o MESMO filtro: o número mostrado na
    # confirmação tem de ser exatamente o que será transmitido.
    livre = _pedido_triagem(sessao_teste, numero_pedido_ol="00000000000000000001")
    _, ana = _cliente(sessao_teste, "Operador Logístico", "ana@teste.com")
    _em_analise_por(sessao_teste, _outro_pedido(sessao_teste, livre, "00000000000000000002"), ana)
    client, _ = _cliente(sessao_teste, "Operador Logístico", "bruno@teste.com")

    resposta = client.get("/pedidos/lote/transmitir/preview", params={"apenas_sem_ocorrencia": False})

    assert resposta.status_code == 200
    assert resposta.json()["total"] == 1


def test_lote_transmitir_continua_incluindo_pedido_com_status_nulo(sessao_teste, logs):
    # Regressão do filtro: `status != 'Em Analise'` sozinho descarta linhas com
    # status NULL (NULL != x é NULL no SQL). O filtro tem de tratar NULL à parte.
    _pedido_triagem(sessao_teste, numero_pedido_ol="00000000000000000001", status_operacional=None)
    client, _ = _cliente(sessao_teste, "Operador Logístico", "ana@teste.com")

    resposta = client.get("/pedidos/lote/transmitir/preview", params={"apenas_sem_ocorrencia": False})

    assert resposta.json()["total"] == 1


def test_lote_reprocessar_ignora_pedido_em_analise_e_nao_derruba_a_analise(sessao_teste, logs, monkeypatch):
    livre = _pedido_triagem(sessao_teste, numero_pedido_ol="00000000000000000001")
    _, ana = _cliente(sessao_teste, "Operador Logístico", "ana@teste.com")
    analisado = _em_analise_por(
        sessao_teste, _outro_pedido(sessao_teste, livre, "00000000000000000002"), ana
    )
    client, _ = _cliente(sessao_teste, "Operador Logístico", "bruno@teste.com")
    reprocessados: list[str] = []

    def reprocessa(pedido_db, id_usuario):
        reprocessados.append(pedido_db.numero_pedido_ol)
        return {"sucesso": True, "mensagem": "ok"}

    monkeypatch.setattr(operacoes, "executar_reprocessar", reprocessa)

    preview = client.get("/pedidos/lote/reprocessar/preview")
    resposta = client.post("/pedidos/lote/reprocessar", json={})

    assert preview.json()["total"] == 1
    assert resposta.status_code == 200
    assert reprocessados == ["00000000000000000001"]
    atual = _recarregar(sessao_teste, analisado)
    # Nem "Aguardando Reprocessamento": a fila em lote não encosta no pedido analisado.
    assert atual.status_operacional == EM_ANALISE
    assert atual.id_usuario_analise == ana.id


# ------------------------- janela entre "ler o status" e "gravar Transmitindo"

def test_marcar_transmitindo_recusa_pedido_que_esta_em_analise(sessao_teste):
    pedido = _pedido_triagem(sessao_teste)
    _, ana = _cliente(sessao_teste, "Operador Logístico", "ana@teste.com")
    _em_analise_por(sessao_teste, pedido, ana)

    assert _marcar_transmitindo(pedido, sessao_teste) is False
    assert _recarregar(sessao_teste, pedido).status_operacional == EM_ANALISE


def test_marcar_transmitindo_funciona_para_pedido_livre(sessao_teste):
    pedido = _pedido_triagem(sessao_teste)

    assert _marcar_transmitindo(pedido, sessao_teste) is True
    assert _recarregar(sessao_teste, pedido).status_operacional == TipoStatusOper.TRANSMITINDO.value


def test_lote_nao_transmite_pedido_que_entrou_em_analise_depois_de_a_lista_ser_montada(sessao_teste, monkeypatch):
    # No lote a lista de pedidos é montada UMA vez e o loop leva o tempo de
    # copiar todos os arquivos: outro operador pode marcar "Em Analise" nesse
    # meio-tempo. O objeto em memória continua com o status antigo — quem decide
    # é o UPDATE condicional no banco.
    pedido = _pedido_triagem(sessao_teste)
    _, ana = _cliente(sessao_teste, "Operador Logístico", "ana@teste.com")
    chamou: list[bool] = []
    monkeypatch.setattr(operacoes, "executar_transmitir", lambda p, u: chamou.append(True))
    sessao_teste.query(Pedido).filter(Pedido.id == pedido.id).update(
        {"status_operacional": EM_ANALISE, "id_usuario_analise": ana.id}, synchronize_session=False
    )
    sessao_teste.commit()

    item = _transmitir_pedido(pedido, sessao_teste, usuario_id=1)

    assert item.sucesso is False
    assert "em análise" in item.mensagem
    assert chamou == []
    assert _recarregar(sessao_teste, pedido).status_operacional == EM_ANALISE


# ------------------------------------------------ autoria nas respostas da API

def test_confeccao_mostra_quem_esta_analisando_so_no_pedido_em_analise(sessao_teste, logs):
    livre = _pedido_triagem(sessao_teste, numero_pedido_ol="00000000000000000001")
    _, ana = _cliente(sessao_teste, "Operador Logístico", "ana@teste.com")
    _em_analise_por(sessao_teste, _outro_pedido(sessao_teste, livre, "00000000000000000002"), ana)
    client, _ = _cliente(sessao_teste, "Gerente Comercial", "gerente@teste.com")  # qualquer perfil lê a triagem

    resposta = client.get("/pedidos/confeccao")

    assert resposta.status_code == 200
    corpo = resposta.json()
    por_numero = {i["numero_pedido_ol"]: i for i in corpo["items"]}
    analisado = por_numero["00000000000000000002"]
    assert analisado["status_operacional"] == EM_ANALISE
    assert analisado["em_analise_por"] == ana.nome
    assert analisado["id_usuario_analise"] == ana.id
    assert analisado["em_analise_desde"] is not None
    assert por_numero["00000000000000000001"]["em_analise_por"] is None
    assert corpo["contagem_por_status"][EM_ANALISE] == 1


def test_detalhe_do_pedido_expoe_autoria_enquanto_em_analise(sessao_teste, logs):
    pedido = _pedido_triagem(sessao_teste)
    client, ana = _cliente(sessao_teste, "Operador Logístico", "ana@teste.com")
    _em_analise_por(sessao_teste, pedido, ana)

    corpo = client.get(f"/pedidos/{pedido.id}").json()

    assert corpo["status_operacional"] == EM_ANALISE
    assert corpo["id_usuario_analise"] == ana.id
    assert corpo["em_analise_por"] == ana.nome
    assert corpo["em_analise_desde"] is not None


def test_detalhe_do_pedido_nao_expoe_autoria_fora_de_analise(sessao_teste, logs):
    # Durante o encerramento o status já é "Reprocessando" mas as colunas ainda
    # estão preenchidas: a API só mostra o selo enquanto o status é Em Analise.
    pedido = _pedido_triagem(sessao_teste)
    client, ana = _cliente(sessao_teste, "Operador Logístico", "ana@teste.com")
    _em_analise_por(sessao_teste, pedido, ana)
    sessao_teste.query(Pedido).filter(Pedido.id == pedido.id).update(
        {"status_operacional": TipoStatusOper.REPROCESSANDO.value}, synchronize_session=False
    )
    sessao_teste.commit()

    corpo = client.get(f"/pedidos/{pedido.id}").json()

    assert corpo["status_operacional"] == TipoStatusOper.REPROCESSANDO.value
    assert corpo["id_usuario_analise"] is None
    assert corpo["em_analise_por"] is None
    assert corpo["em_analise_desde"] is None


# ------------------------------------------------------------- selo "Analisado"
#
# Depois que a análise encerra COM SUCESSO o pedido ganha um selo com QUEM
# analisou e QUANDO (Pedido.analisado_por / analisado_em). Diferente de
# id_usuario_analise / em_analise_desde (a trava da análise em curso, que volta
# a NULL), o selo persiste: é o rastro para os outros usuários verem que o
# pedido já passou por análise humana — em Triagem, Rastreamento, Histórico,
# detalhe e planilhas.

import io

import pandas as pd

from ol_core.models.enums.tipo_status_erp import TipoStatusErp


def _marcar_analisado(sessao_teste, pedido: Pedido, usuario: Usuario, quando: datetime | None = None) -> Pedido:
    """Estado pré-existente do teste: pedido que já teve a análise concluída."""
    pedido.analisado_por = usuario.id
    pedido.analisado_em = quando or datetime(2026, 10, 7, 14, 32)
    sessao_teste.commit()
    return _recarregar(sessao_teste, pedido)


def _xlsx(resposta) -> pd.DataFrame:
    assert resposta.status_code == 200, resposta.text
    return pd.read_excel(io.BytesIO(resposta.content))


def test_encerrar_com_sucesso_grava_o_selo_e_libera_a_trava(sessao_teste, logs, monkeypatch):
    pedido = _pedido_triagem(sessao_teste)
    client, ana = _cliente(sessao_teste, "Operador Logístico", "ana@teste.com")
    _em_analise_por(sessao_teste, pedido, ana)
    monkeypatch.setattr(operacoes, "executar_reprocessar", _reprocessar_falso(sessao_teste, TipoStatusOper.PRONTO.value))
    antes = datetime.now()

    resposta = client.delete(f"/pedidos/{pedido.id}/analise")

    assert resposta.status_code == 200
    atual = _recarregar(sessao_teste, pedido)
    assert atual.analisado_por == ana.id
    assert atual.analisado_em is not None and atual.analisado_em >= antes.replace(microsecond=0)
    # a trava continua sendo liberada: o selo NÃO reaproveita essas colunas
    assert atual.id_usuario_analise is None
    assert atual.em_analise_desde is None


def test_selo_nasce_mesmo_quando_o_pedido_volta_para_verificar(sessao_teste, logs, monkeypatch):
    # O selo diz "um humano analisou", não "o pedido está sem ocorrência".
    pedido = _pedido_triagem(sessao_teste)
    client, ana = _cliente(sessao_teste, "Operador Logístico", "ana@teste.com")
    _em_analise_por(sessao_teste, pedido, ana)
    monkeypatch.setattr(operacoes, "executar_reprocessar", _reprocessar_falso(sessao_teste, TipoStatusOper.VERIFICAR.value))

    assert client.delete(f"/pedidos/{pedido.id}/analise").status_code == 200

    atual = _recarregar(sessao_teste, pedido)
    assert atual.status_operacional == TipoStatusOper.VERIFICAR.value
    assert atual.analisado_por == ana.id
    assert atual.analisado_em is not None


def test_encerrar_com_falha_nao_grava_o_selo(sessao_teste, logs, monkeypatch):
    pedido = _pedido_triagem(sessao_teste)
    client, ana = _cliente(sessao_teste, "Operador Logístico", "ana@teste.com")
    _em_analise_por(sessao_teste, pedido, ana)

    def levanta(pedido_db, id_usuario):
        raise ValueError("Arquivo 'X.txt' não encontrado na pasta de backup.")

    monkeypatch.setattr(operacoes, "executar_reprocessar", levanta)

    assert client.delete(f"/pedidos/{pedido.id}/analise").status_code == 422

    atual = _recarregar(sessao_teste, pedido)
    assert atual.status_operacional == EM_ANALISE
    assert atual.analisado_por is None
    assert atual.analisado_em is None


def test_iniciar_analise_nao_apaga_o_selo_da_analise_anterior(sessao_teste, logs):
    pedido = _pedido_triagem(sessao_teste)
    client, ana = _cliente(sessao_teste, "Operador Logístico", "ana@teste.com")
    anterior = datetime(2026, 10, 1, 9, 0)
    _marcar_analisado(sessao_teste, pedido, ana, anterior)

    assert client.post(f"/pedidos/{pedido.id}/analise").status_code == 200

    atual = _recarregar(sessao_teste, pedido)
    assert atual.status_operacional == EM_ANALISE
    assert atual.analisado_por == ana.id
    assert atual.analisado_em == anterior


def test_nova_analise_sobrescreve_o_selo_com_a_ultima(sessao_teste, logs, monkeypatch):
    pedido = _pedido_triagem(sessao_teste)
    _, ana = _cliente(sessao_teste, "Operador Logístico", "ana@teste.com")
    bia_client, bia = _cliente(sessao_teste, "Operador Logístico", "bia@teste.com")
    _marcar_analisado(sessao_teste, pedido, ana, datetime(2026, 10, 1, 9, 0))
    _em_analise_por(sessao_teste, pedido, bia)
    monkeypatch.setattr(operacoes, "executar_reprocessar", _reprocessar_falso(sessao_teste, TipoStatusOper.PRONTO.value))

    assert bia_client.delete(f"/pedidos/{pedido.id}/analise").status_code == 200

    atual = _recarregar(sessao_teste, pedido)
    assert atual.analisado_por == bia.id
    assert atual.analisado_em > datetime(2026, 10, 1, 9, 0)


def test_confeccao_expoe_o_selo_depois_da_analise_encerrada_e_vem_vazio_para_quem_nunca_foi_analisado(sessao_teste, logs):
    livre = _pedido_triagem(sessao_teste, numero_pedido_ol="00000000000000000001")
    _, ana = _cliente(sessao_teste, "Operador Logístico", "ana@teste.com")
    quando = datetime(2026, 10, 7, 14, 32)
    _marcar_analisado(sessao_teste, _outro_pedido(sessao_teste, livre, "00000000000000000002"), ana, quando)
    client, _ = _cliente(sessao_teste, "Gerente Comercial", "gerente@teste.com")  # qualquer perfil vê o selo

    corpo = client.get("/pedidos/confeccao").json()

    por_numero = {i["numero_pedido_ol"]: i for i in corpo["items"]}
    analisado = por_numero["00000000000000000002"]
    assert analisado["analisado_por"] == ana.nome
    assert analisado["analisado_em"].startswith("2026-10-07T14:32")
    assert analisado["em_analise_por"] is None               # análise já acabou
    assert por_numero["00000000000000000001"]["analisado_por"] is None
    assert por_numero["00000000000000000001"]["analisado_em"] is None


def test_confeccao_mantem_o_selo_enquanto_uma_nova_analise_esta_em_curso(sessao_teste, logs):
    pedido = _pedido_triagem(sessao_teste)
    _, ana = _cliente(sessao_teste, "Operador Logístico", "ana@teste.com")
    bia_client, bia = _cliente(sessao_teste, "Operador Logístico", "bia@teste.com")
    _marcar_analisado(sessao_teste, pedido, ana)
    _em_analise_por(sessao_teste, pedido, bia)

    item = bia_client.get("/pedidos/confeccao").json()["items"][0]

    assert item["em_analise_por"] == bia.nome       # quem está com o pedido agora
    assert item["analisado_por"] == ana.nome        # quem analisou por último


def test_confeccao_filtra_por_analisado(sessao_teste, logs):
    base = _pedido_triagem(sessao_teste, numero_pedido_ol="00000000000000000001")
    _, ana = _cliente(sessao_teste, "Operador Logístico", "ana@teste.com")
    _marcar_analisado(sessao_teste, _outro_pedido(sessao_teste, base, "00000000000000000002"), ana)
    _outro_pedido(sessao_teste, base, "00000000000000000003")
    client, _ = _cliente(sessao_teste, "Operador Logístico", "op@teste.com")

    def numeros(**params):
        corpo = client.get("/pedidos/confeccao", params=params).json()
        return {i["numero_pedido_ol"] for i in corpo["items"]}

    assert numeros() == {"00000000000000000001", "00000000000000000002", "00000000000000000003"}
    assert numeros(analisado="true") == {"00000000000000000002"}
    assert numeros(analisado="false") == {"00000000000000000001", "00000000000000000003"}


def test_detalhe_do_pedido_expoe_o_selo_mesmo_fora_de_analise(sessao_teste, logs):
    pedido = _pedido_triagem(sessao_teste)
    client, ana = _cliente(sessao_teste, "Operador Logístico", "ana@teste.com")
    _marcar_analisado(sessao_teste, pedido, ana)

    corpo = client.get(f"/pedidos/{pedido.id}").json()

    assert corpo["analisado_por"] == ana.nome
    assert corpo["analisado_em"].startswith("2026-10-07T14:32")
    detalhes = client.get(f"/pedidos/{pedido.id}/detalhes").json()
    assert detalhes["analisado_por"] == ana.nome


def test_selo_persiste_no_rastreamento_e_no_historico(sessao_teste, logs):
    base = _pedido_triagem(sessao_teste, numero_pedido_ol="00000000000000000001", status_erp=TipoStatusErp.TRANSMITIDO.value)
    _, ana = _cliente(sessao_teste, "Operador Logístico", "ana@teste.com")
    _marcar_analisado(sessao_teste, base, ana)
    concluido = _outro_pedido(
        sessao_teste, base, "00000000000000000002", status_erp=TipoStatusErp.PROCESSO_CONCLUIDO.value,
    )
    _marcar_analisado(sessao_teste, concluido, ana)
    client, _ = _cliente(sessao_teste, "Gerente Comercial", "gerente@teste.com")

    rastreamento = client.get("/pedidos/rastreamento").json()["items"]
    historico = client.get("/pedidos/historico").json()["items"]

    assert [(i["numero_pedido_ol"], i["analisado_por"]) for i in rastreamento] == [("00000000000000000001", ana.nome)]
    assert [(i["numero_pedido_ol"], i["analisado_por"]) for i in historico] == [("00000000000000000002", ana.nome)]
    assert rastreamento[0]["analisado_em"].startswith("2026-10-07T14:32")
    assert historico[0]["analisado_em"].startswith("2026-10-07T14:32")


def test_export_da_triagem_tem_as_colunas_do_selo_e_respeita_o_filtro(sessao_teste, logs):
    base = _pedido_triagem(sessao_teste, numero_pedido_ol="00000000000000000001")
    _, ana = _cliente(sessao_teste, "Operador Logístico", "ana@teste.com")
    _marcar_analisado(sessao_teste, _outro_pedido(sessao_teste, base, "00000000000000000002"), ana)
    client, _ = _cliente(sessao_teste, "Operador Logístico", "op@teste.com")

    tudo = _xlsx(client.get("/pedidos/confeccao/export")).set_index("Pedido OL")
    so_analisados = _xlsx(client.get("/pedidos/confeccao/export", params={"analisado": "true"}))

    assert list(tudo.columns[-2:]) == ["Analisado Por", "Analisado Em"]   # no fim da planilha
    assert tudo.loc[2, "Analisado Por"] == ana.nome
    assert pd.isna(tudo.loc[1, "Analisado Por"]) and pd.isna(tudo.loc[1, "Analisado Em"])
    assert list(so_analisados["Pedido OL"]) == [2]                         # planilha bate com a tela


def test_export_do_rastreamento_tem_as_colunas_do_selo(sessao_teste, logs):
    pedido = _pedido_triagem(sessao_teste, status_erp=TipoStatusErp.TRANSMITIDO.value)
    client, ana = _cliente(sessao_teste, "Operador Logístico", "ana@teste.com")
    _marcar_analisado(sessao_teste, pedido, ana)

    planilha = _xlsx(client.get("/pedidos/rastreamento/export"))

    assert list(planilha.columns[-2:]) == ["Analisado Por", "Analisado Em"]
    assert planilha.loc[0, "Analisado Por"] == ana.nome


def test_export_do_historico_funciona_com_filtros_e_tem_as_colunas_do_selo(sessao_teste, logs):
    # Regressão: o export chamava _filtrar_historico com os argumentos fora de
    # ordem (nome_arquivo no lugar de industria_nome etc.) e devolvia erro.
    pedido = _pedido_triagem(
        sessao_teste,
        status_erp=TipoStatusErp.PROCESSO_CONCLUIDO.value,
        data_pedido=datetime(2026, 10, 5, 10, 0),
    )
    client, ana = _cliente(sessao_teste, "Operador Logístico", "ana@teste.com")
    _marcar_analisado(sessao_teste, pedido, ana)
    periodo = {"data_inicio": "2026-10-01", "data_fim": "2026-10-31"}

    sem_filtro = _xlsx(client.get("/pedidos/historico/export", params=periodo))
    com_filtros = _xlsx(client.get(
        "/pedidos/historico/export",
        params={**periodo, "nome_arquivo": pedido.nome_arquivo, "industria_nome": "Industria Teste",
                "status_erp": TipoStatusErp.PROCESSO_CONCLUIDO.value},
    ))
    outra_industria = client.get("/pedidos/historico/export", params={**periodo, "industria_nome": "Outra"})

    assert list(sem_filtro.columns[-2:]) == ["Analisado Por", "Analisado Em"]
    assert sem_filtro.loc[0, "Analisado Por"] == ana.nome
    assert len(com_filtros) == 1
    assert outra_industria.status_code == 200 and len(pd.read_excel(io.BytesIO(outra_industria.content))) == 0
