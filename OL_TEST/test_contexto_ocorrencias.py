"""Testes de ol_core.database.mysql.contexto_ocorrencias.registrar_ocorrencia.

Segue a convenção do OL_TEST (ver conftest.py): monkeypatch aponta pro nome como
foi importado dentro do módulo testado (contexto_ocorrencias.inserir). Nenhum
teste aqui toca o MySQL de verdade.

O que se trava: o INSERT grava o `resolvido` do próprio Erro. Quando o parâmetro
de ignorar uma validação está ligado, o validador devolve resolvido="ignorado"
(VARCHAR(100)) com severidade IGNORADO — gravar 0 fixo (como já foi) mantinha o pedido em
"Verificar" por causa de uma ocorrência que deveria estar ignorada.
"""
from ol_core.database.mysql import contexto_ocorrencias
from ol_core.models.enums.tipo_severidade import TipoSeveridade
from ol_core.models.erro import Erro, RESOLVIDO_IGNORADO


def _captura_insert(monkeypatch) -> list[tuple]:
    chamadas: list[tuple] = []
    monkeypatch.setattr(contexto_ocorrencias, "inserir", lambda sql, args=None: chamadas.append(args))
    return chamadas


def test_registrar_ocorrencia_grava_resolvido_ignorado_e_severidade_ignorado(monkeypatch):
    chamadas = _captura_insert(monkeypatch)
    erro = Erro(
        numero_pedido_ol="PED1",
        descricao="Cliente 123 não está cadastrado no sistema",
        severidade=TipoSeveridade.IGNORADO.value,
        resolvido=RESOLVIDO_IGNORADO,
    )

    contexto_ocorrencias.registrar_ocorrencia(erro)

    (numero, severidade, _codigo, _descricao, resolvido, _criado_em), = chamadas
    assert numero == "PED1"
    assert severidade == "IGNORADO"
    assert resolvido == "ignorado"


def test_registrar_ocorrencia_aberta_continua_gravando_resolvido_0(monkeypatch):
    chamadas = _captura_insert(monkeypatch)
    erro = Erro(numero_pedido_ol="PED1", descricao="x", severidade=TipoSeveridade.ERRO.value, resolvido=0)

    contexto_ocorrencias.registrar_ocorrencia(erro)

    assert chamadas[0][4] == "0"


def test_registrar_ocorrencia_aceita_resolvido_booleano(monkeypatch):
    chamadas = _captura_insert(monkeypatch)

    contexto_ocorrencias.registrar_ocorrencia(Erro(numero_pedido_ol="PED1", descricao="x", resolvido=True))
    contexto_ocorrencias.registrar_ocorrencia(Erro(numero_pedido_ol="PED1", descricao="x", resolvido=False))

    assert [c[4] for c in chamadas] == ["1", "0"]


def test_registrar_ocorrencia_nao_propaga_erro_de_banco(monkeypatch):
    def _levanta(sql, args=None):
        raise RuntimeError("falha simulada")

    monkeypatch.setattr(contexto_ocorrencias, "inserir", _levanta)

    # Comportamento já existente: falha ao gravar ocorrência não derruba o fluxo.
    contexto_ocorrencias.registrar_ocorrencia(Erro(numero_pedido_ol="PED1", descricao="x"))
