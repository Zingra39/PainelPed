"""Testes de ol_core.services.cancelamento_service.gerar_cancelado_closeup.

IMPORTANTE — bug corrigido nesta task (mesma família do bug documentado em
test_retorno_service.py e test_espelho_service.py): o bloco "except"
referenciava variáveis (numero_pedido_ol, id_arquivo) que só eram atribuídas
no meio do "try" — corrigido inicializando as duas como None antes do try
(ver test_erro_real_antes_de_id_arquivo_ser_definido_deveria_retornar_false_sem_quebrar).
Ver OL_TEST/README.md.
"""
import pytest

from ol_core.services import cancelamento_service
from ol_core.models.enums.tipo_status_erp import TipoStatusErp
from ol_core.models.enums.tipo_status_oper import TipoStatusOper
from .conftest import criar_industria, criar_pedido, criar_item


def _preparar_mocks_de_infraestrutura(monkeypatch, id_arquivo_existente=None):
    # CNPJ do distribuidor vem da tabela `parametro` (tela de Parametrização).
    monkeypatch.setattr(cancelamento_service, "exigir_cnpj_distribuidor", lambda: "11222333000181")
    monkeypatch.setattr(cancelamento_service, "verificar_cancelado_existente", lambda numero_pedido_ol: id_arquivo_existente)
    monkeypatch.setattr(cancelamento_service, "registrar_arquivo", lambda arquivo, situacao: 1)
    monkeypatch.setattr(cancelamento_service, "atualizar_situacao_arquivo", lambda id_arquivo, situacao: None)
    monkeypatch.setattr(cancelamento_service, "atualizar_status_pedido", lambda numero_pedido_ol, status: None)
    monkeypatch.setattr(cancelamento_service, "atualizar_status_erp_pedido", lambda numero_pedido_ol, status_erp: None)
    monkeypatch.setattr(cancelamento_service, "envia_arquivo_para_pasta", lambda origem, destino: None)
    monkeypatch.setattr(cancelamento_service, "valida_ean", lambda numero_pedido_ol, codigo_produto, ean: ean)
    monkeypatch.setattr(cancelamento_service, "valida_motivo", lambda item, pedido, cnpj: 0)
    # O motivo vem do ERP e é gravado no MySQL. Antes estes testes chegavam ao
    # SQL Server de verdade e só passavam porque a falha de conexão era
    # engolida (virava "sem motivo"); agora ela propaga (ErroConexaoBanco).
    monkeypatch.setattr(cancelamento_service, "verifica_motivo_cancelamento", lambda codigo_interno_pedido: None)
    monkeypatch.setattr(cancelamento_service, "atualizar_motivo_cancelamento_pedido", lambda numero_pedido_ol, motivo: None)
    # Sem isso, testes que nao mockam explicitamente as fontes de itens (via
    # _mockar_fontes_de_itens) cairiam na consulta real ao MySQL — nenhum
    # teste aqui pode tocar infraestrutura de verdade.
    monkeypatch.setattr(cancelamento_service, "verificar_itens_pedido_pelo_nome_arquivo_mysql", lambda nome_arquivo: None)


def _mockar_fontes_de_itens(monkeypatch, itens_sql, itens_mysql):
    """Troca as duas fontes de dados de verificar_itens_pedido_cancelamento
    pelos valores dados (None simula 'sem itens' na fonte)."""
    monkeypatch.setattr(cancelamento_service, "verifica_itens_pedido_pelo_cod_pedido", lambda codigo_interno_pedido: itens_sql)
    monkeypatch.setattr(cancelamento_service, "verificar_itens_pedido_pelo_nome_arquivo_mysql", lambda nome_arquivo: itens_mysql)


# --------------------------------------------------------------------- verificar_itens_pedido_cancelamento — merge SQL Server + MySQL
# Bug corrigido nesta task: o cancelamento buscava itens SÓ no Delage (SQL
# Server) via verifica_itens_pedido_pelo_cod_pedido — se o Delage não tivesse
# NENHUM item pro pedido (produto não cadastrado lá), o cancelamento falhava
# (FALHA_CANCELAMENTO) mesmo com os itens presentes no MySQL/painel. Mesma
# família do bug já corrigido em retorno_service.verificar_itens_pedido (ver
# test_retorno_service.py) — lógica de merge extraída pra
# ol_core.services.merge_itens_pedido.combinar_itens_sql_e_mysql e reaproveitada
# aqui.

def test_delage_sem_itens_usa_mysql_como_fallback(monkeypatch):
    item_mysql = criar_item(ean="ean-so-no-mysql")
    _mockar_fontes_de_itens(monkeypatch, itens_sql=None, itens_mysql=[item_mysql])

    pedido = criar_pedido(nome_arquivo="PEDIDO_TESTE.txt")
    resultado = cancelamento_service.verificar_itens_pedido_cancelamento(pedido)

    assert resultado == [item_mysql]


def test_mysql_sem_itens_usa_delage_como_fallback(monkeypatch):
    item_sql = criar_item(ean="ean-so-no-sql")
    _mockar_fontes_de_itens(monkeypatch, itens_sql=[item_sql], itens_mysql=None)

    pedido = criar_pedido(nome_arquivo="PEDIDO_TESTE.txt")
    resultado = cancelamento_service.verificar_itens_pedido_cancelamento(pedido)

    assert resultado == [item_sql]


def test_intersecao_usa_a_versao_do_delage_para_itens_em_comum(monkeypatch):
    item_sql = criar_item(ean="ean-comum", preco=99.0)
    item_mysql = criar_item(ean="ean-comum", preco=1.0)
    _mockar_fontes_de_itens(monkeypatch, itens_sql=[item_sql], itens_mysql=[item_mysql])

    pedido = criar_pedido(nome_arquivo="PEDIDO_TESTE.txt")
    resultado = cancelamento_service.verificar_itens_pedido_cancelamento(pedido)

    assert len(resultado) == 1
    assert resultado[0].preco == 99.0  # veio do Delage, nao do MySQL


def test_ambas_fontes_sem_itens_retorna_lista_vazia(monkeypatch):
    _mockar_fontes_de_itens(monkeypatch, itens_sql=None, itens_mysql=None)

    pedido = criar_pedido(nome_arquivo="PEDIDO_TESTE.txt")
    resultado = cancelamento_service.verificar_itens_pedido_cancelamento(pedido)

    assert resultado == []


def test_gerar_cancelado_closeup_usa_itens_do_mysql_quando_delage_nao_tem_o_pedido(monkeypatch, tmp_path):
    # Reproduz o caminho completo: Delage sem item para o pedido, mas o
    # painel (MySQL) tem os dados originais — o cancelamento deve ser gerado
    # normalmente, em vez de cair na guard clause de FALHA_CANCELAMENTO.
    _preparar_mocks_de_infraestrutura(monkeypatch)
    item_mysql = criar_item(ean="ean-so-no-mysql")
    _mockar_fontes_de_itens(monkeypatch, itens_sql=None, itens_mysql=[item_mysql])

    industria = criar_industria(tmp_path)
    pedido = criar_pedido(nome_arquivo="PEDIDO_TESTE_12345678000199.txt")
    from datetime import datetime
    pedido.data_cancelamento = datetime.now()

    resultado = cancelamento_service.gerar_cancelado_closeup(industria, pedido)

    assert resultado is True
    arquivos_gerados = list((tmp_path / "cancelamento").glob("CANCELAMENTO_*.TXT"))
    assert len(arquivos_gerados) == 1


# --------------------------------------------------------------------- guard clause normal (sem bug)

def test_gerar_cancelado_closeup_sem_itens_retorna_false(monkeypatch, tmp_path):
    _preparar_mocks_de_infraestrutura(monkeypatch)
    monkeypatch.setattr(cancelamento_service, "verifica_itens_pedido_pelo_cod_pedido", lambda codigo_interno_pedido: [])

    industria = criar_industria(tmp_path)
    pedido = criar_pedido()

    resultado = cancelamento_service.gerar_cancelado_closeup(industria, pedido)

    assert resultado is False


def test_gerar_cancelado_closeup_sem_itens_reflete_falha_na_situacao_do_arquivo(monkeypatch, tmp_path):
    # Bug encontrado nesta task: esta guard clause já marcava o PEDIDO como
    # "Falha no Cancelamento" (atualizar_status_pedido), mas nunca atualizava
    # a situação do ARQUIVO já registrado (id_arquivo) — que ficava travada
    # em "Cancelamento Sendo Gerado" pra sempre, mesmo com o pedido em falha.
    _preparar_mocks_de_infraestrutura(monkeypatch)
    chamadas = []
    monkeypatch.setattr(
        cancelamento_service, "atualizar_situacao_arquivo",
        lambda id_arquivo, situacao: chamadas.append((id_arquivo, situacao)),
    )
    monkeypatch.setattr(cancelamento_service, "verifica_itens_pedido_pelo_cod_pedido", lambda codigo_interno_pedido: [])

    industria = criar_industria(tmp_path)
    pedido = criar_pedido()

    resultado = cancelamento_service.gerar_cancelado_closeup(industria, pedido)

    assert resultado is False
    assert chamadas == [(1, TipoStatusOper.FALHA_CANCELAMENTO.value)]


# --------------------------------------------------------------------- caminho feliz (sem bug)

def test_gerar_cancelado_closeup_com_itens_validos_gera_o_arquivo_com_sucesso(monkeypatch, tmp_path):
    _preparar_mocks_de_infraestrutura(monkeypatch)
    monkeypatch.setattr(
        cancelamento_service, "verifica_itens_pedido_pelo_cod_pedido",
        lambda codigo_interno_pedido: [criar_item()],
    )

    industria = criar_industria(tmp_path)
    pedido = criar_pedido()
    from datetime import datetime
    pedido.data_cancelamento = datetime.now()

    resultado = cancelamento_service.gerar_cancelado_closeup(industria, pedido)

    assert resultado is True
    arquivos_gerados = list((tmp_path / "cancelamento").glob("CANCELAMENTO_*.TXT"))
    assert len(arquivos_gerados) == 1


def test_gerar_cancelado_closeup_com_sucesso_move_status_erp_para_pedido_cancelado(monkeypatch, tmp_path):
    # Card "usar status_erp de forma mais adequada": Cancelamento gerado =
    # fluxo encerrado — status_erp deve virar "Pedido Cancelado".
    _preparar_mocks_de_infraestrutura(monkeypatch)
    chamadas = []
    monkeypatch.setattr(
        cancelamento_service, "atualizar_status_erp_pedido",
        lambda numero_pedido_ol, status_erp: chamadas.append((numero_pedido_ol, status_erp)),
    )
    monkeypatch.setattr(
        cancelamento_service, "verifica_itens_pedido_pelo_cod_pedido",
        lambda codigo_interno_pedido: [criar_item()],
    )

    industria = criar_industria(tmp_path)
    pedido = criar_pedido()
    from datetime import datetime
    pedido.data_cancelamento = datetime.now()

    resultado = cancelamento_service.gerar_cancelado_closeup(industria, pedido)

    assert resultado is True
    assert chamadas
    assert all(c == (pedido.numero_pedido_ol, TipoStatusErp.PEDIDO_CANCELADO.value) for c in chamadas)


# --------------------------------------------------------------------- bug conhecido: UnboundLocalError no except
def test_pasta_cancelamento_invalida_deveria_retornar_false_sem_quebrar(monkeypatch, tmp_path):
    _preparar_mocks_de_infraestrutura(monkeypatch)
    industria = criar_industria(tmp_path)
    industria.pasta_cancelamento = None
    pedido = criar_pedido()

    resultado = cancelamento_service.gerar_cancelado_closeup(industria, pedido)

    assert resultado is False


def test_erro_antes_de_id_arquivo_ser_definido_deveria_retornar_false_sem_quebrar(monkeypatch, tmp_path):
    _preparar_mocks_de_infraestrutura(monkeypatch)

    def trata_textos_com_falha(*args, **kwargs):
        print(f"Erro ao tratar texto {args}")
        return "<Error>"

    monkeypatch.setattr(cancelamento_service, "trata_textos", trata_textos_com_falha)

    industria = criar_industria(tmp_path)
    pedido = criar_pedido()

    resultado = cancelamento_service.gerar_cancelado_closeup(industria, pedido)

    assert resultado is False


def test_erro_real_antes_de_id_arquivo_ser_definido_deveria_retornar_false_sem_quebrar(monkeypatch, tmp_path):
    # Diferente do teste acima (trata_textos devolvendo "<Error>", que faz um
    # "return False" controlado sem nunca chegar no "except"), este forca uma
    # excecao DE VERDADE (os.makedirs) antes de numero_pedido_ol/id_arquivo
    # serem atribuidos — o cenario que de fato exercitava o UnboundLocalError
    # documentado no topo do arquivo. Com as duas inicializadas como None
    # antes do try, o "except" consegue tratar o erro e devolver False.
    _preparar_mocks_de_infraestrutura(monkeypatch)

    def levanta_oserror(caminho):
        raise OSError("disco cheio simulado")

    monkeypatch.setattr(cancelamento_service.os, "makedirs", levanta_oserror)

    industria = criar_industria(tmp_path)
    industria.pasta_cancelamento = str(tmp_path / "cancelamento_inexistente")
    pedido = criar_pedido()

    resultado = cancelamento_service.gerar_cancelado_closeup(industria, pedido)

    assert resultado is False
