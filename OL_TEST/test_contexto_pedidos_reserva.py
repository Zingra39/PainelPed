"""B7: `reservar_status_pedido` troca o status num único UPDATE condicional
(compare-and-set), em vez de ler e depois gravar. Aqui só se confere o SQL
montado e a leitura do número de linhas alteradas — nada toca o MySQL."""
from ol_core.database.mysql import contexto_pedidos
from ol_core.models.enums.tipo_status_oper import TipoStatusOper


def _captura(monkeypatch, linhas: int):
    chamadas = []

    def fake(sql, args):
        chamadas.append((sql, args))
        return linhas

    monkeypatch.setattr(contexto_pedidos, "executar_contando", fake)
    return chamadas


def test_reserva_bloqueia_status_em_geracao_no_proprio_update(monkeypatch):
    chamadas = _captura(monkeypatch, 1)

    assert contexto_pedidos.reservar_status_pedido("123", TipoStatusOper.GERANDO_RETORNO.value) is True

    sql, args = chamadas[0]
    assert sql.startswith("UPDATE pedido SET status_operacional")
    assert "NOT IN (%s, %s, %s)" in sql
    assert "status_operacional = %s" not in sql.split("WHERE", 1)[1]
    assert args[0] == TipoStatusOper.GERANDO_RETORNO.value
    assert args[2] == "123"
    assert set(args[3:6]) == set(contexto_pedidos.STATUS_EM_GERACAO)
    # Trava abandonada: expira o que está parado há mais que o limite.
    assert "OR atualizado_em < %s" in sql
    assert args[6] == args[1] - contexto_pedidos.TRAVA_GERACAO_EXPIRA


def test_reserva_com_status_esperado_compara_o_status_atual(monkeypatch):
    chamadas = _captura(monkeypatch, 1)

    contexto_pedidos.reservar_status_pedido(
        "123", TipoStatusOper.GERANDO_ESPELHO.value, status_esperado=TipoStatusOper.AGUARDANDO_ESPELHO.value
    )

    sql, args = chamadas[0]
    assert sql.rstrip().endswith("AND status_operacional = %s")
    assert args[-1] == TipoStatusOper.AGUARDANDO_ESPELHO.value


def test_reserva_sem_linha_alterada_devolve_false(monkeypatch):
    _captura(monkeypatch, 0)
    assert contexto_pedidos.reservar_status_pedido("123", TipoStatusOper.GERANDO_RETORNO.value) is False


def test_reserva_com_erro_de_sql_devolve_false(monkeypatch):
    def quebra(sql, args):
        raise RuntimeError("sql inválido")

    monkeypatch.setattr(contexto_pedidos, "executar_contando", quebra)
    assert contexto_pedidos.reservar_status_pedido("123", TipoStatusOper.GERANDO_RETORNO.value) is False
