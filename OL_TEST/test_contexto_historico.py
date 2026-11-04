"""Testes de ol_core.database.mysql.contexto_historico.obter_id_usuario_sistema
— usuário "Sistema" (ativo=0, sem login) referenciado em pedido_historico
quando a ação é automática, ex: transmissão automática do parâmetro
`transmissao_automatica_pronto` (Card de parametrização, squad review
2026-09-17).

registrar_historico (pré-existente, não alterado por este Card) não é
recoberto aqui — o foco é só a função nova.
"""
from ol_core.database.mysql import contexto_historico


def _resetar_cache(monkeypatch):
    # O id do usuário "Sistema" é cacheado em memória (não muda em runtime).
    # Cada teste precisa começar com o cache limpo, senão o resultado de um
    # teste "vaza" pro próximo.
    monkeypatch.setattr(contexto_historico, "_id_usuario_sistema_cache", None)


def test_obter_id_usuario_sistema_retorna_o_id_quando_o_usuario_existe(monkeypatch):
    _resetar_cache(monkeypatch)
    monkeypatch.setattr(contexto_historico, "buscar_um", lambda sql, args=None: {"id": 7})

    assert contexto_historico.obter_id_usuario_sistema() == 7


def test_obter_id_usuario_sistema_retorna_none_quando_o_usuario_nao_existe(monkeypatch):
    _resetar_cache(monkeypatch)
    monkeypatch.setattr(contexto_historico, "buscar_um", lambda sql, args=None: None)

    assert contexto_historico.obter_id_usuario_sistema() is None


def test_obter_id_usuario_sistema_retorna_none_em_caso_de_erro_de_banco(monkeypatch):
    _resetar_cache(monkeypatch)

    def _levanta(sql, args=None):
        raise RuntimeError("falha simulada de conexão")

    monkeypatch.setattr(contexto_historico, "buscar_um", _levanta)

    assert contexto_historico.obter_id_usuario_sistema() is None


def test_obter_id_usuario_sistema_so_consulta_o_banco_uma_vez_por_processo(monkeypatch):
    _resetar_cache(monkeypatch)
    chamadas = []

    def _buscar_um(sql, args=None):
        chamadas.append(1)
        return {"id": 7}

    monkeypatch.setattr(contexto_historico, "buscar_um", _buscar_um)

    primeiro = contexto_historico.obter_id_usuario_sistema()
    segundo = contexto_historico.obter_id_usuario_sistema()

    assert primeiro == segundo == 7
    assert len(chamadas) == 1  # a segunda chamada veio do cache, não do banco
