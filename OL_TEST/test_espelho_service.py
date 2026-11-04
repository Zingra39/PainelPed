"""Testes de ol_core.services.espelho_service.gerar_espelho_closeup.

IMPORTANTE — bugs encontrados durante a escrita destes testes (ver
OL_TEST/README.md pra mais detalhes):

1. Industria.pasta_nfe cai num valor padrao Path("ERP/NF") quando não
   configurada, diferente de TODAS as outras pastas do model (que ficam
   None). Isso faz o guard "if not PASTA_OUTPUT: raise ValueError(...)"
   dentro de gerar_espelho_closeup ser inalcançável via construção normal.
2. O mesmo padrão de UnboundLocalError do retorno_service acontecia aqui —
   corrigido nesta task inicializando numero_pedido_ol/id_arquivo como None
   antes do try (ver
   test_erro_real_antes_de_id_arquivo_ser_definido_deveria_retornar_false_sem_quebrar).
"""
from pathlib import Path

import pytest

from ol_core.services import espelho_service
from ol_core.models.industria import Industria
from ol_core.models.enums.tipo_layout import TipoLayout
from ol_core.models.enums.tipo_status_erp import TipoStatusErp
from ol_core.models.enums.tipo_status_oper import TipoStatusOper
from .conftest import criar_industria, criar_titulo, criar_titulo_item


def _preparar_mocks_de_infraestrutura(monkeypatch, id_arquivo_existente=None):
    # CNPJ do distribuidor vem da tabela `parametro` (tela de Parametrização).
    monkeypatch.setattr(espelho_service, "exigir_cnpj_distribuidor", lambda: "11222333000181")
    monkeypatch.setattr(espelho_service, "verificar_espelho_existente", lambda numero_pedido_ol: id_arquivo_existente)
    monkeypatch.setattr(espelho_service, "registrar_arquivo", lambda arquivo, situacao: 1)
    monkeypatch.setattr(espelho_service, "atualizar_situacao_arquivo", lambda id_arquivo, situacao: None)
    monkeypatch.setattr(espelho_service, "atualizar_status_pedido", lambda numero_pedido_ol, status: None)
    monkeypatch.setattr(espelho_service, "atualizar_status_erp_pedido", lambda numero_pedido_ol, status_erp: None)
    monkeypatch.setattr(espelho_service, "envia_arquivo_para_pasta", lambda origem, destino: None)
    monkeypatch.setattr(espelho_service, "valida_ean", lambda numero_pedido_ol, codigo_produto, ean: ean)


# --------------------------------------------------------------------- bug do valor padrão de pasta_nfe
def test_industria_pasta_nfe_nao_configurada_deveria_ficar_none_como_as_outras_pastas(monkeypatch):
    monkeypatch.setattr(Industria, "_criar_pastas", lambda self: None)  # evita criar pastas de verdade no cwd

    industria = Industria(id_industria=1, nome="Industria Teste", tipo_layout=TipoLayout.CLOSEUP)

    assert industria.pasta_envio_retorno is None
    assert industria.pasta_nfe is None


def test_gerar_espelho_closeup_sem_pasta_nfe_configurada_deveria_retornar_false_sem_quebrar(monkeypatch, tmp_path):
    _preparar_mocks_de_infraestrutura(monkeypatch)
    industria = criar_industria(tmp_path)
    industria.pasta_nfe = None  # contorna manualmente o valor padrão indevido testado acima
    titulo = criar_titulo()

    resultado = espelho_service.gerar_espelho_closeup(industria, titulo)

    assert resultado is False


# --------------------------------------------------------------------- guard clauses normais (sem bug)

def test_gerar_espelho_closeup_sem_itens_registrados_retorna_false(monkeypatch, tmp_path):
    _preparar_mocks_de_infraestrutura(monkeypatch)
    monkeypatch.setattr(espelho_service, "verifica_titulo_itens", lambda codigo_titulo: None)

    industria = criar_industria(tmp_path)
    titulo = criar_titulo()

    resultado = espelho_service.gerar_espelho_closeup(industria, titulo)

    assert resultado is False


def test_gerar_espelho_closeup_sem_itens_registrados_reflete_falha_na_situacao_do_arquivo(monkeypatch, tmp_path):
    # Bug encontrado nesta task: esta guard clause já marcava o PEDIDO como
    # "Falha no Espelho" (atualizar_status_pedido), mas nunca atualizava a
    # situação do ARQUIVO já registrado (id_arquivo) — que ficava travada em
    # "Espelho Sendo Gerado" pra sempre, mesmo com o pedido em falha.
    _preparar_mocks_de_infraestrutura(monkeypatch)
    chamadas = []
    monkeypatch.setattr(
        espelho_service, "atualizar_situacao_arquivo",
        lambda id_arquivo, situacao: chamadas.append((id_arquivo, situacao)),
    )
    monkeypatch.setattr(espelho_service, "verifica_titulo_itens", lambda codigo_titulo: None)

    industria = criar_industria(tmp_path)
    titulo = criar_titulo()

    resultado = espelho_service.gerar_espelho_closeup(industria, titulo)

    assert resultado is False
    assert chamadas == [(1, TipoStatusOper.FALHA_ESPELHO.value)]


def test_erro_antes_de_id_arquivo_ser_definido_deveria_retornar_false_sem_quebrar(monkeypatch, tmp_path):
    _preparar_mocks_de_infraestrutura(monkeypatch)

    def trata_textos_com_falha(*args, **kwargs):
        print(f"Erro ao tratar texto {args}")
        return "<Error>"

    monkeypatch.setattr(espelho_service, "trata_textos", trata_textos_com_falha)

    industria = criar_industria(tmp_path)
    titulo = criar_titulo()

    resultado = espelho_service.gerar_espelho_closeup(industria, titulo)

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

    monkeypatch.setattr(espelho_service.os, "makedirs", levanta_oserror)

    industria = criar_industria(tmp_path)
    industria.pasta_nfe = str(tmp_path / "nfe_inexistente")
    titulo = criar_titulo()

    resultado = espelho_service.gerar_espelho_closeup(industria, titulo)

    assert resultado is False


# --------------------------------------------------------------------- itens com produtos_motivo != 0

def test_item_com_motivo_e_quantidade_atendida_zero_e_desconsiderado_do_arquivo(monkeypatch, tmp_path):
    _preparar_mocks_de_infraestrutura(monkeypatch)
    item_normal = criar_titulo_item(codigo_produto=1, ean="7890000000001", quantidade_atendida=10, produtos_motivo=0)
    item_com_motivo = criar_titulo_item(codigo_produto=2, ean="7890000000002", quantidade_atendida=0, produtos_motivo=5)
    monkeypatch.setattr(espelho_service, "verifica_titulo_itens", lambda codigo_titulo: [item_normal, item_com_motivo])

    industria = criar_industria(tmp_path)
    titulo = criar_titulo()

    resultado = espelho_service.gerar_espelho_closeup(industria, titulo)

    assert resultado is True
    caminho = Path(industria.pasta_nfe) / f"ESPELHO_{titulo.numero_pedido_ol}_{titulo.cnpj_cliente}.TXT"
    linhas_itens = [l for l in caminho.read_text().splitlines() if l.startswith("2")]
    assert len(linhas_itens) == 1


def test_gerar_espelho_closeup_com_sucesso_move_status_erp_para_processo_concluido(monkeypatch, tmp_path):
    # Card "usar status_erp de forma mais adequada": Espelho gerado = pedido
    # faturado, fluxo encerrado — status_erp deve virar "Processo Concluido".
    _preparar_mocks_de_infraestrutura(monkeypatch)
    chamadas = []
    monkeypatch.setattr(
        espelho_service, "atualizar_status_erp_pedido",
        lambda numero_pedido_ol, status_erp: chamadas.append((numero_pedido_ol, status_erp)),
    )
    item_normal = criar_titulo_item(codigo_produto=1, ean="7890000000001", quantidade_atendida=10, produtos_motivo=0)
    monkeypatch.setattr(espelho_service, "verifica_titulo_itens", lambda codigo_titulo: [item_normal])

    industria = criar_industria(tmp_path)
    titulo = criar_titulo()

    resultado = espelho_service.gerar_espelho_closeup(industria, titulo)

    assert resultado is True
    assert chamadas
    assert all(c == (titulo.numero_pedido_ol, TipoStatusErp.PROCESSO_CONCLUIDO.value) for c in chamadas)



def test_item_com_quantidade_atendida_maior_que_zero_e_menor_que_quantidade_solicitada(monkeypatch, tmp_path):
    _preparar_mocks_de_infraestrutura(monkeypatch)
    item = criar_titulo_item(codigo_produto=1, ean="7890000000001", quantidade_atendida=4, quantidade_solicitada=10,produtos_motivo=0)
    monkeypatch.setattr(espelho_service, "verifica_titulo_itens", lambda codigo_titulo: [item])

    industria = criar_industria(tmp_path)
    titulo = criar_titulo()

    resultado = espelho_service.gerar_espelho_closeup(industria, titulo)

    assert resultado is True
    caminho = Path(industria.pasta_nfe) / f"ESPELHO_{titulo.numero_pedido_ol}_{titulo.cnpj_cliente}.TXT"
    linhas_itens = [l for l in caminho.read_text().splitlines() if l.startswith("2")]
    # Itera na lista e verifica se codigo da motivo é 9 para o item com motivo != 0 e quantidade_atendida > 0
    for linha in linhas_itens:
        if linha[1:14] == item.ean:
            cod_motivo = linha[52:79].strip()
            assert cod_motivo == "9"
    
def test_item_com_codigo_motivo_de_corte(monkeypatch, tmp_path):
    _preparar_mocks_de_infraestrutura(monkeypatch)
    item_normal = criar_titulo_item(codigo_produto=1, ean="7890000000001", quantidade_atendida=10, quantidade_solicitada=10, produtos_motivo=0)
    item_com_motivo = criar_titulo_item(codigo_produto=2, ean="7890000000002", quantidade_atendida=10, quantidade_solicitada=10, produtos_motivo=5)
    monkeypatch.setattr(espelho_service, "verifica_titulo_itens", lambda codigo_titulo: [item_normal, item_com_motivo])

    industria = criar_industria(tmp_path)
    titulo = criar_titulo()

    resultado = espelho_service.gerar_espelho_closeup(industria, titulo)

    assert resultado is True
    caminho = Path(industria.pasta_nfe) / f"ESPELHO_{titulo.numero_pedido_ol}_{titulo.cnpj_cliente}.TXT"
    linhas_itens = [l for l in caminho.read_text().splitlines() if l.startswith("2")]
    assert len(linhas_itens) == 1


# --------------------------------------------------------------------- EAN > 13 dígitos de produto repetido
# Correção: o "último produto incluído" nunca era atualizado (ficava sempre 0),
# então a regra não descartava nada (só itens de produto com código 0).

def _linhas_itens_do_espelho(monkeypatch, tmp_path, itens):
    _preparar_mocks_de_infraestrutura(monkeypatch)
    monkeypatch.setattr(espelho_service, "verifica_titulo_itens", lambda codigo_titulo: itens)
    industria = criar_industria(tmp_path)
    titulo = criar_titulo()

    assert espelho_service.gerar_espelho_closeup(industria, titulo) is True

    caminho = Path(industria.pasta_nfe) / f"ESPELHO_{titulo.numero_pedido_ol}_{titulo.cnpj_cliente}.TXT"
    return [l for l in caminho.read_text().splitlines() if l.startswith("2")]


def test_ean_longo_do_mesmo_produto_do_item_anterior_nao_repete_no_espelho(monkeypatch, tmp_path):
    itens = [
        criar_titulo_item(codigo_produto=1, ean="7890000000001"),
        criar_titulo_item(codigo_produto=1, ean="78900000000011234"),  # mesmo produto, EAN longo: fica de fora
        criar_titulo_item(codigo_produto=2, ean="7890000000002"),
    ]

    linhas = _linhas_itens_do_espelho(monkeypatch, tmp_path, itens)

    assert len(linhas) == 2


def test_ean_longo_de_produto_diferente_entra_no_espelho(monkeypatch, tmp_path):
    itens = [
        criar_titulo_item(codigo_produto=1, ean="7890000000001"),
        criar_titulo_item(codigo_produto=2, ean="78900000000021234"),
    ]

    assert len(_linhas_itens_do_espelho(monkeypatch, tmp_path, itens)) == 2


def test_ean_longo_de_produto_codigo_zero_nao_e_mais_descartado(monkeypatch, tmp_path):
    itens = [criar_titulo_item(codigo_produto=0, ean="78900000000001234")]

    assert len(_linhas_itens_do_espelho(monkeypatch, tmp_path, itens)) == 1


def test_ean_curto_do_mesmo_produto_continua_entrando(monkeypatch, tmp_path):
    # A regra só vale para EAN com mais de 13 dígitos.
    itens = [
        criar_titulo_item(codigo_produto=1, ean="7890000000001"),
        criar_titulo_item(codigo_produto=1, ean="7890000000001"),
    ]

    assert len(_linhas_itens_do_espelho(monkeypatch, tmp_path, itens)) == 2
