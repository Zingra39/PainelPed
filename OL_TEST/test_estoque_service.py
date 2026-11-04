"""Testes de ol_core.services.estoque_service.gerar_estoque_closeup.

A funcao nao devolve nada (sempre None, sucesso ou erro) — os testes
verificam o efeito colateral (arquivo escrito em disco) e as chamadas
mockadas, igual ao padrao dos outros *_service.py.
"""
import pandas as pd

from ol_core.database.mysql.contexto_parametros import ConfiguracaoAusente
from ol_core.services import estoque_service
from .conftest import criar_industria

CNPJ_TESTE = "11222333000181"
FORNECEDORES_TESTE = [10423, 10425]


def _mockar_configuracao(monkeypatch, fornecedores=FORNECEDORES_TESTE):
    """CNPJ (tabela `parametro`) e fornecedores (tabela `industria_fornecedor`)."""
    monkeypatch.setattr(estoque_service, "exigir_cnpj_distribuidor", lambda: CNPJ_TESTE)
    monkeypatch.setattr(estoque_service, "buscar_fornecedores_industria", lambda id_industria: list(fornecedores))


def _preparar_mocks_de_infraestrutura(monkeypatch):
    monkeypatch.setattr(estoque_service, "envia_arquivo_para_pasta", lambda origem, destino: None)
    _mockar_configuracao(monkeypatch)


def test_gerar_estoque_closeup_gera_arquivo_com_registros_ordenados_pela_chave(monkeypatch, tmp_path):
    _preparar_mocks_de_infraestrutura(monkeypatch)

    # fora de ordem de propósito — "9999990" (chave "99999900010") deve vir
    # depois de "1112220" (chave "11122200005") no arquivo final
    df_estoque = pd.DataFrame({
        "Cod_barra": ["9999990", "1112220"],
        "estoque_disponivel": ["00010", "00005"],
    })
    monkeypatch.setattr(estoque_service, "resgata_estoque", lambda fornecedores: df_estoque)

    industria = criar_industria(tmp_path, pasta_estoque=str(tmp_path / "estoque"))

    estoque_service.gerar_estoque_closeup(industria, pedido=None)

    caminho = industria.pasta_estoque / "ESTOQUE_P_HYPERA_CAC.TXT"
    assert caminho.exists()
    linhas = caminho.read_text().splitlines()

    # CNPJ do distribuidor vem da Parametrização (antes era fixo no código).
    assert linhas[0].startswith("1" + CNPJ_TESTE)
    assert linhas[1] == "2111222000005"
    assert linhas[2] == "2999999000010"


def test_gerar_estoque_closeup_erro_ao_resgatar_estoque_nao_propaga_excecao(monkeypatch, tmp_path):
    _preparar_mocks_de_infraestrutura(monkeypatch)

    def resgata_estoque_com_erro(fornecedores):
        raise RuntimeError("falha simulada de conexão com o ERP")

    monkeypatch.setattr(estoque_service, "resgata_estoque", resgata_estoque_com_erro)

    industria = criar_industria(tmp_path, pasta_estoque=str(tmp_path / "estoque"))

    # não deve levantar exceção nenhuma pro chamador
    estoque_service.gerar_estoque_closeup(industria, pedido=None)

    caminho = industria.pasta_estoque / "ESTOQUE_P_HYPERA_CAC.TXT"
    assert not caminho.exists()


def test_gerar_estoque_closeup_com_sucesso_envia_arquivo_para_pasta_da_industria(monkeypatch, tmp_path):
    chamadas_envio = []
    monkeypatch.setattr(
        estoque_service, "envia_arquivo_para_pasta",
        lambda origem, destino: chamadas_envio.append((origem, destino)),
    )
    _mockar_configuracao(monkeypatch)
    df_estoque = pd.DataFrame({"Cod_barra": ["1"], "estoque_disponivel": ["5"]})
    monkeypatch.setattr(estoque_service, "resgata_estoque", lambda fornecedores: df_estoque)

    industria = criar_industria(tmp_path, pasta_estoque=str(tmp_path / "estoque"))

    estoque_service.gerar_estoque_closeup(industria, pedido=None)

    assert len(chamadas_envio) == 1
    origem, destino = chamadas_envio[0]
    assert origem == industria.pasta_estoque / "ESTOQUE_P_HYPERA_CAC.TXT"
    assert destino == industria.pasta_estoque


def test_gerar_estoque_closeup_consulta_so_os_fornecedores_da_industria(monkeypatch, tmp_path):
    _preparar_mocks_de_infraestrutura(monkeypatch)
    recebidos = []

    def resgata(fornecedores):
        recebidos.append(fornecedores)
        return pd.DataFrame({"Cod_barra": ["1"], "estoque_disponivel": ["5"]})

    monkeypatch.setattr(estoque_service, "resgata_estoque", resgata)

    estoque_service.gerar_estoque_closeup(criar_industria(tmp_path, pasta_estoque=str(tmp_path / "estoque")), pedido=None)

    assert recebidos == [FORNECEDORES_TESTE]


def test_gerar_estoque_closeup_sem_fornecedor_cadastrado_nao_gera_arquivo(monkeypatch, tmp_path):
    """Sem fornecedor não há filtro de produto: o arquivo levaria o estoque do
    ERP inteiro para a indústria. Nem consulta, nem arquivo."""
    _preparar_mocks_de_infraestrutura(monkeypatch)
    _mockar_configuracao(monkeypatch, fornecedores=[])
    consultas = []
    monkeypatch.setattr(estoque_service, "resgata_estoque", lambda fornecedores: consultas.append(1))

    industria = criar_industria(tmp_path, pasta_estoque=str(tmp_path / "estoque"))
    estoque_service.gerar_estoque_closeup(industria, pedido=None)

    assert consultas == []
    assert not (industria.pasta_estoque / "ESTOQUE_P_HYPERA_CAC.TXT").exists()


def test_gerar_estoque_closeup_sem_cnpj_configurado_nao_gera_arquivo(monkeypatch, tmp_path):
    _preparar_mocks_de_infraestrutura(monkeypatch)

    def sem_cnpj():
        raise ConfiguracaoAusente("CNPJ do distribuidor não configurado.")

    monkeypatch.setattr(estoque_service, "exigir_cnpj_distribuidor", sem_cnpj)
    monkeypatch.setattr(
        estoque_service, "resgata_estoque",
        lambda fornecedores: pd.DataFrame({"Cod_barra": ["1"], "estoque_disponivel": ["5"]}),
    )

    industria = criar_industria(tmp_path, pasta_estoque=str(tmp_path / "estoque"))
    estoque_service.gerar_estoque_closeup(industria, pedido=None)

    assert not (industria.pasta_estoque / "ESTOQUE_P_HYPERA_CAC.TXT").exists()
