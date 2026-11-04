"""Testes de integração REAIS contra o MySQL de homologação.

Só chama funções de LEITURA de `ol_core.database.mysql.*` (nenhum
INSERT/UPDATE/DELETE) e usa identificadores que sabidamente não existem
na base, então o resultado esperado é sempre "não encontrado" — o que já
é suficiente para provar que a função conecta, monta a query certa e
processa o retorno do MySQL de verdade sem estourar exceção.

Pulados automaticamente (via fixture `mysql_homolog_disponivel`) se o
MySQL de homologação não estiver alcançável a partir de onde os testes
rodarem.
"""
import pytest

from ol_core.database.mysql.contexto_arquivo import (
    verifica_se_arquivo_existe,
    verificar_cancelado_existente,
    verificar_retorno_existente,
    verificar_espelho_existente,
    verifica_se_arquivo_baixado_existe,
)
from ol_core.database.mysql.contexto_pedidos import (
    verifica_pedido_existente,
    obter_id_pedido,
    pode_reprocessar,
    verificar_ean_pedido_coletado,
    verifica_dados_pedido,
    verificar_itens_pedido_pelo_nome_arquivo_mysql,
)
from ol_core.database.mysql.contexto_industria import (
    buscar_industrias_ativas,
    buscar_industria_ftp,
)
from ol_core.database.mysql.contexto_ocorrencias import buscar_ocorrencias_nao_resolvidas

_NOME_ARQUIVO_INEXISTENTE = "ARQUIVO_QUE_NAO_EXISTE_AUDITORIA_XYZ.TXT"
_PEDIDO_INEXISTENTE = "PEDIDO_INEXISTENTE_AUDITORIA_XYZ"
_EAN_INEXISTENTE = "0000000000000"
_ID_INDUSTRIA_INEXISTENTE = 999999999


def test_verifica_se_arquivo_existe_com_arquivo_inexistente_retorna_false(mysql_homolog_disponivel):
    assert verifica_se_arquivo_existe(_NOME_ARQUIVO_INEXISTENTE) is False


def test_verificar_cancelado_existente_com_pedido_inexistente_retorna_none(mysql_homolog_disponivel):
    assert verificar_cancelado_existente(_PEDIDO_INEXISTENTE) is None


def test_verificar_retorno_existente_com_pedido_inexistente_retorna_none(mysql_homolog_disponivel):
    assert verificar_retorno_existente(_PEDIDO_INEXISTENTE) is None


def test_verificar_espelho_existente_com_pedido_inexistente_retorna_none(mysql_homolog_disponivel):
    assert verificar_espelho_existente(_PEDIDO_INEXISTENTE) is None


def test_verifica_se_arquivo_baixado_existe_com_arquivo_inexistente_retorna_false(mysql_homolog_disponivel):
    assert verifica_se_arquivo_baixado_existe(_NOME_ARQUIVO_INEXISTENTE) is False


def test_verifica_pedido_existente_com_arquivo_inexistente_retorna_false(mysql_homolog_disponivel):
    assert verifica_pedido_existente(_NOME_ARQUIVO_INEXISTENTE) is False


def test_obter_id_pedido_com_arquivo_inexistente_retorna_none(mysql_homolog_disponivel):
    assert obter_id_pedido(_NOME_ARQUIVO_INEXISTENTE) is None


def test_pode_reprocessar_com_pedido_inexistente_retorna_tupla(mysql_homolog_disponivel):
    resultado = pode_reprocessar(_PEDIDO_INEXISTENTE)
    assert isinstance(resultado, tuple)
    assert len(resultado) == 2
    podeOuNao, _motivo = resultado
    assert isinstance(podeOuNao, bool)


def test_verificar_ean_pedido_coletado_com_pedido_inexistente_retorna_false(mysql_homolog_disponivel):
    assert verificar_ean_pedido_coletado(_PEDIDO_INEXISTENTE, _EAN_INEXISTENTE) is False


def test_verifica_dados_pedido_com_pedido_inexistente_retorna_false(mysql_homolog_disponivel):
    assert verifica_dados_pedido(_PEDIDO_INEXISTENTE) is False


def test_verificar_itens_pedido_pelo_nome_arquivo_mysql_com_arquivo_inexistente_retorna_none_ou_vazio(mysql_homolog_disponivel):
    resultado = verificar_itens_pedido_pelo_nome_arquivo_mysql(_NOME_ARQUIVO_INEXISTENTE)
    assert resultado is None or resultado == []


def test_buscar_industrias_ativas_retorna_lista(mysql_homolog_disponivel):
    resultado = buscar_industrias_ativas()
    assert isinstance(resultado, list)


def test_buscar_industria_ftp_com_id_inexistente_retorna_none(mysql_homolog_disponivel):
    assert buscar_industria_ftp(_ID_INDUSTRIA_INEXISTENTE) is None


def test_buscar_ocorrencias_nao_resolvidas_com_pedido_inexistente_retorna_lista_vazia(mysql_homolog_disponivel):
    resultado = buscar_ocorrencias_nao_resolvidas(_PEDIDO_INEXISTENTE)
    assert isinstance(resultado, list)
    assert resultado == []
