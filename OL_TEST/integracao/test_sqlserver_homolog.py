"""Testes de integração REAIS contra o SQL Server do ERP (homologação).

Todas as funções de `ol_core.database.sqlserver.*` já são SOMENTE
LEITURA por natureza (conforme o comentário "somente leitura" ao lado
das credenciais ERP_* no .env) — mesmo assim, nenhum teste aqui grava
nada, só consulta.

Atenção: as funções desta camada capturam qualquer exceção internamente
(`_consultar_dataframe`/`_consultar_linha`) e devolvem DataFrame vazio /
None em vez de propagar o erro — por isso o gate de "está alcançável"
é feito à parte, na fixture `sqlserver_homolog_disponivel` (conexão
pyodbc direta), não a partir do retorno das funções testadas.

Pulados automaticamente se o SQL Server do ERP não estiver alcançável,
OU se o driver ODBC do sistema (usado por pyodbc/SQLAlchemy em
produção) não estiver instalado no ambiente onde os testes rodarem.
"""
from ol_core.database.sqlserver.contexto_cancelamento import verifica_arquivos_cancelados
from ol_core.database.sqlserver.contexto_cliente import (
    resgatar_cliente,
    resgatar_condicao,
    verificar_condicao,
    verifica_cliente_na_condicao,
    verificar_item_condicao,
)

from ol_core.database.sqlserver.contexto_pedido import (
    verifica_arquivos_transmitidos,
    verifica_itens_pedido_pelo_cod_pedido,
    verifica_itens_pedido_pelo_nome_arquivo,
    verificar_primeiro_pedido,
    verificar_valor_pedido_minimo,
    verifica_pedido,
    verifica_todos_itens_pedido_pelo_cod_pedido,
    verifica_todos_eans_itens_pedido_pelo_nome_arquivo,
)
from ol_core.database.sqlserver.contexto_produto import (
    resgatar_produto,
    resgatar_produtos_por_lote,
    resgatar_produto_na_condicao,
    verifica_tipo_ean,
    verifica_primeiro_ean_valido,
    verifica_estoque_item,
    verifica_estoque_item_pedido,
    verifica_quantidade_que_sera_atendida,
    resgata_estoque,
)
from ol_core.database.sqlserver.contexto_titulo import (
    verificar_emissao_titulos,
    verificar_titulo,
    verifica_titulo_itens,
)

_CNPJ_INEXISTENTE = "01234567890999"
_EAN_INEXISTENTE = "0123456789099"
_CODIGO_PRODUTO_INEXISTENTE = 999999999
_CODIGO_PEDIDO_INEXISTENTE = 999999999
_NOME_ARQUIVO_INEXISTENTE = "ARQUIVO_QUE_NAO_EXISTE_AUDITORIA_XYZ.TXT"
_ID_BBS_INEXISTENTE = 999999999
_DATA_ALVO = "2000-01-01"
_CONDICAO_INEXISTENTE = "CONDICAO_INEXISTENTE_XYZ"
_ID_CONDICAO_INEXISTENTE = 999999999


def test_verifica_arquivos_cancelados_sem_resultado_retorna_none_ou_vazio(sqlserver_homolog_disponivel):
    resultado = verifica_arquivos_cancelados(_ID_BBS_INEXISTENTE, _DATA_ALVO)
    assert resultado is None or resultado == []


def test_resgatar_cliente_com_cnpj_inexistente_retorna_none(sqlserver_homolog_disponivel):
    assert resgatar_cliente(_CNPJ_INEXISTENTE) is None


def test_resgatar_condicao_com_id_inexistente_retorna_none(sqlserver_homolog_disponivel):
    assert resgatar_condicao(_ID_CONDICAO_INEXISTENTE) is None


def test_verificar_condicao_com_condicao_inexistente_nao_estoura_excecao(sqlserver_homolog_disponivel):
    verificar_condicao(_CONDICAO_INEXISTENTE)  # só precisa não lançar


def test_verifica_cliente_na_condicao_com_dados_inexistentes_retorna_false_ou_none(sqlserver_homolog_disponivel):
    resultado = verifica_cliente_na_condicao(_CONDICAO_INEXISTENTE, _CNPJ_INEXISTENTE)
    assert resultado is None or resultado is False


def test_verificar_item_condicao_com_dados_inexistentes_nao_estoura_excecao(sqlserver_homolog_disponivel):
    verificar_item_condicao(_CODIGO_PRODUTO_INEXISTENTE, _CONDICAO_INEXISTENTE)


def test_verifica_arquivos_transmitidos_sem_resultado_retorna_none_ou_vazio(sqlserver_homolog_disponivel):
    resultado = verifica_arquivos_transmitidos(_ID_BBS_INEXISTENTE, _DATA_ALVO)
    assert resultado is None or resultado == []


def test_verifica_itens_pedido_pelo_cod_pedido_com_pedido_inexistente_retorna_none_ou_vazio(sqlserver_homolog_disponivel):
    resultado = verifica_itens_pedido_pelo_cod_pedido(_CODIGO_PEDIDO_INEXISTENTE)
    assert resultado is None or resultado == []


def test_verifica_itens_pedido_pelo_nome_arquivo_com_arquivo_inexistente_retorna_none_ou_vazio(sqlserver_homolog_disponivel):
    resultado = verifica_itens_pedido_pelo_nome_arquivo(_NOME_ARQUIVO_INEXISTENTE)
    assert resultado is None or resultado == []


def test_verificar_primeiro_pedido_com_cliente_inexistente_nao_estoura_excecao(sqlserver_homolog_disponivel):
    verificar_primeiro_pedido(_CNPJ_INEXISTENTE, _DATA_ALVO)


def test_verificar_valor_pedido_minimo_com_condicao_inexistente_retorna_numero(sqlserver_homolog_disponivel):
    resultado = verificar_valor_pedido_minimo(_ID_CONDICAO_INEXISTENTE)
    assert isinstance(resultado, (int, float))


def test_verifica_pedido_com_numero_inexistente_retorna_none_ou_vazio(sqlserver_homolog_disponivel):
    resultado = verifica_pedido(str(_CODIGO_PEDIDO_INEXISTENTE))
    assert resultado is None or resultado == []


def test_verifica_todos_itens_pedido_pelo_cod_pedido_com_pedido_inexistente_retorna_none_ou_vazio(sqlserver_homolog_disponivel):
    resultado = verifica_todos_itens_pedido_pelo_cod_pedido(_CODIGO_PEDIDO_INEXISTENTE)
    assert resultado is None or resultado == []


def test_verifica_todos_eans_itens_pedido_pelo_nome_arquivo_com_arquivo_inexistente_retorna_none_ou_vazio(sqlserver_homolog_disponivel):
    resultado = verifica_todos_eans_itens_pedido_pelo_nome_arquivo(_NOME_ARQUIVO_INEXISTENTE)
    assert resultado is None or resultado == []


def test_resgatar_produto_com_ean_inexistente_retorna_none(sqlserver_homolog_disponivel):
    assert resgatar_produto(_EAN_INEXISTENTE) is None


def test_resgatar_produtos_por_lote_com_eans_inexistentes_retorna_none_ou_vazio(sqlserver_homolog_disponivel):
    resultado = resgatar_produtos_por_lote([_EAN_INEXISTENTE])
    assert resultado is None or resultado == []


def test_resgatar_produto_na_condicao_com_dados_inexistentes_retorna_none(sqlserver_homolog_disponivel):
    assert resgatar_produto_na_condicao(_CODIGO_PRODUTO_INEXISTENTE, _ID_CONDICAO_INEXISTENTE) is None


def test_verifica_tipo_ean_com_produto_inexistente_nao_estoura_excecao(sqlserver_homolog_disponivel):
    verifica_tipo_ean(_CODIGO_PRODUTO_INEXISTENTE)


def test_verifica_primeiro_ean_valido_com_produto_inexistente_retorna_none(sqlserver_homolog_disponivel):
    assert verifica_primeiro_ean_valido(_CODIGO_PRODUTO_INEXISTENTE) is None


def test_verifica_estoque_item_com_produto_inexistente_retorna_false_ou_none(sqlserver_homolog_disponivel):
    resultado = verifica_estoque_item(_CODIGO_PRODUTO_INEXISTENTE)
    assert resultado is None or resultado is False


def test_verifica_estoque_item_pedido_com_produto_inexistente_retorna_false_ou_none(sqlserver_homolog_disponivel):
    resultado = verifica_estoque_item_pedido(_CODIGO_PRODUTO_INEXISTENTE)
    assert resultado is None or resultado is False


def test_verifica_quantidade_que_sera_atendida_com_produto_inexistente_nao_estoura_excecao(sqlserver_homolog_disponivel):
    verifica_quantidade_que_sera_atendida(_CODIGO_PRODUTO_INEXISTENTE)


def test_resgata_estoque_retorna_dataframe(sqlserver_homolog_disponivel):
    import pandas as pd
    resultado = resgata_estoque()
    assert isinstance(resultado, pd.DataFrame)


def test_verificar_emissao_titulos_sem_resultado_retorna_none_ou_vazio(sqlserver_homolog_disponivel):
    resultado = verificar_emissao_titulos(_ID_BBS_INEXISTENTE, _DATA_ALVO)
    assert resultado is None or resultado == []


def test_verificar_titulo_com_arquivo_inexistente_retorna_none_ou_vazio(sqlserver_homolog_disponivel):
    resultado = verificar_titulo(_NOME_ARQUIVO_INEXISTENTE)
    assert resultado is None or resultado == []


def test_verifica_titulo_itens_com_titulo_inexistente_retorna_none_ou_vazio(sqlserver_homolog_disponivel):
    resultado = verifica_titulo_itens(_CODIGO_PEDIDO_INEXISTENTE)
    assert resultado is None or resultado == []
