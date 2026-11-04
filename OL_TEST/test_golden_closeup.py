"""Golden files do layout Close-Up: rede de segurança do formato dos arquivos.

Cada teste gera um arquivo (retorno, espelho, cancelamento, estoque) com dados
FIXOS — banco, ERP e FTP trocados por stubs, data/hora congelada — e compara
com o arquivo de referência em OL_TEST/golden/closeup/. A leitura do pedido
faz o caminho inverso: lê um arquivo fixo e compara o Pedido resultante com
um JSON de referência.

Os arquivos de referência foram gerados a partir do código ANTES de o formato
ser movido para ol_core/layouts (Auditoria, seção 4.3, passo 1). Qualquer
mudança de posição, largura ou preenchimento quebra estes testes.

Para regenerar (só quando a mudança de formato for intencional e acordada com
a indústria):  OL_GOLDEN_ATUALIZAR=1 pytest OL_TEST/test_golden_closeup.py
"""
import json
import os
from datetime import datetime as _datetime
from pathlib import Path

import pandas as pd
import pytest

from ol_core.services import cancelamento_service, espelho_service, estoque_service, retorno_service
from ol_core.utils import conversor
from .conftest import criar_industria, criar_item, criar_pedido, criar_titulo, criar_titulo_item

GOLDEN = Path(__file__).resolve().parent / "golden" / "closeup"
ATUALIZAR = os.getenv("OL_GOLDEN_ATUALIZAR") == "1"
CNPJ_DISTRIBUIDOR = "46239901000131"
NUMERO = "2026102900123456787P"


class _Agora(_datetime):
    """datetime com now() congelado (estoque e fallbacks usam a hora atual)."""

    @classmethod
    def now(cls, tz=None):
        return cls(2026, 11, 3, 14, 5, 9)


def _comparar_com_golden(gerado: Path, nome_golden: str) -> None:
    # Só o fim de linha é normalizado (CRLF no Windows, LF no Linux); o resto é byte a byte.
    conteudo = gerado.read_bytes().replace(b"\r\n", b"\n")
    golden = GOLDEN / nome_golden
    if ATUALIZAR:
        golden.parent.mkdir(parents=True, exist_ok=True)
        golden.write_bytes(conteudo)
    assert golden.exists(), f"Golden {golden} não existe (gere com OL_GOLDEN_ATUALIZAR=1)."
    assert conteudo == golden.read_bytes(), f"{gerado.name} difere do golden {nome_golden}"


def _stubs_comuns(monkeypatch, modulo):
    monkeypatch.setattr(modulo, "exigir_cnpj_distribuidor", lambda: CNPJ_DISTRIBUIDOR)
    monkeypatch.setattr(modulo, "registrar_arquivo", lambda arquivo, situacao: 1)
    monkeypatch.setattr(modulo, "atualizar_situacao_arquivo", lambda *a: None)
    monkeypatch.setattr(modulo, "atualizar_status_pedido", lambda *a: None)
    monkeypatch.setattr(modulo, "atualizar_status_erp_pedido", lambda *a: None)
    monkeypatch.setattr(modulo, "envia_arquivo_ftp", lambda *a: None)
    monkeypatch.setattr(modulo, "envia_arquivo_para_pasta", lambda *a: None)
    # valida_ean consulta o ERP; aqui devolve o EAN como veio.
    monkeypatch.setattr(modulo, "valida_ean", lambda numero, codigo_produto, ean: ean)


def _itens_pedido():
    return [
        criar_item(numero_pedido_ol=NUMERO, codigo_produto=101, ean="7891234567895",
                   quantidade_solicitada=10, quantidade_atendida=10, desconto=12.5, cod_motivo=0),
        criar_item(numero_pedido_ol=NUMERO, codigo_produto=102, ean="789123",
                   quantidade_solicitada=24, quantidade_atendida=7, desconto=33.335, cod_motivo=9),
        criar_item(numero_pedido_ol=NUMERO, codigo_produto=103, ean="7890000000017",
                   quantidade_solicitada=3, quantidade_atendida=0, desconto=0.0, cod_motivo=17),
    ]


def test_golden_retorno(monkeypatch, tmp_path):
    _stubs_comuns(monkeypatch, retorno_service)
    monkeypatch.setattr(retorno_service, "verificar_retorno_existente", lambda numero: None)
    monkeypatch.setattr(retorno_service, "verificar_itens_pedido", lambda nome: _itens_pedido())
    monkeypatch.setattr(retorno_service, "valida_motivo", lambda item, pedido, cnpj: item.cod_motivo)
    monkeypatch.setattr(retorno_service, "marcar_ocorrencias_resolvidas", lambda n: None)
    monkeypatch.setattr(retorno_service, "marcar_ocorrencias_item_resolvidas", lambda n: None)
    industria = criar_industria(tmp_path, pasta_envio_retorno=str(tmp_path / "envio_retorno"))
    pedido = criar_pedido(
        numero_pedido_ol=NUMERO, cnpj_cliente="57.107.095/0001-64", codigo_interno_pedido=4567,
        nome_arquivo=f"PEDIDO_{NUMERO}_57107095000164.txt", data_pedido=_datetime(2026, 10, 29, 8, 30, 15),
    )

    assert retorno_service.gerar_retorno_closeup(industria, pedido) is True

    _comparar_com_golden(Path(industria.pasta_retorno) / f"RETORNO_{NUMERO}_57107095000164.TXT", "retorno.txt")


def test_golden_espelho(monkeypatch, tmp_path):
    _stubs_comuns(monkeypatch, espelho_service)
    monkeypatch.setattr(espelho_service, "verificar_espelho_existente", lambda numero: None)
    itens = [
        criar_titulo_item(codigo_produto=101, ean="7891234567895", quantidade_atendida=10,
                          quantidade_solicitada=10, desconto=12.5, preco=8.9, produtos_motivo=0),
        criar_titulo_item(codigo_produto=102, ean="789123", quantidade_atendida=7,
                          quantidade_solicitada=24, desconto=33.335, preco=21.333, produtos_motivo=None),
        criar_titulo_item(codigo_produto=103, ean="7890000000017", quantidade_atendida=0,
                          quantidade_solicitada=3, produtos_motivo=0),           # fora: nada atendido
        criar_titulo_item(codigo_produto=104, ean="7890000000024", quantidade_atendida=5,
                          quantidade_solicitada=5, produtos_motivo=7),           # fora: motivo do ERP
        criar_titulo_item(codigo_produto=105, ean="78900000000311234", quantidade_atendida=2,
                          quantidade_solicitada=2, desconto=1.0, preco=3.0, produtos_motivo=19),
    ]
    monkeypatch.setattr(espelho_service, "verifica_titulo_itens", lambda codigo: itens)
    industria = criar_industria(tmp_path, pasta_envio_nf=str(tmp_path / "envio_nf"))
    titulo = criar_titulo(
        numero_pedido_ol=NUMERO, cnpj_cliente="57107095000164", codigo_pedido_interno=4567,
        data_emissao=_datetime(2026, 10, 30, 16, 42, 5, 987654), data_vencimento="2026-11-29",
        codigo_titulo=88, numero_titulo="123456", serie_nf=1, chave_acesso="35261046239901000131550010001234561123456780",
    )

    assert espelho_service.gerar_espelho_closeup(industria, titulo) is True

    _comparar_com_golden(Path(industria.pasta_nfe) / f"ESPELHO_{NUMERO}_57107095000164.TXT", "espelho.txt")


def test_golden_cancelamento(monkeypatch, tmp_path):
    _stubs_comuns(monkeypatch, cancelamento_service)
    monkeypatch.setattr(cancelamento_service, "verificar_cancelado_existente", lambda numero: None)
    monkeypatch.setattr(cancelamento_service, "verificar_itens_pedido_cancelamento", lambda pedido: _itens_pedido())
    monkeypatch.setattr(cancelamento_service, "valida_motivo", lambda item, pedido, cnpj: item.cod_motivo)
    monkeypatch.setattr(cancelamento_service, "verifica_motivo_cancelamento", lambda codigo: "Cliente desistiu")
    monkeypatch.setattr(cancelamento_service, "atualizar_motivo_cancelamento_pedido", lambda *a: None)
    industria = criar_industria(tmp_path)
    pedido = criar_pedido(
        numero_pedido_ol=NUMERO, cnpj_cliente="57107095000164", codigo_interno_pedido=4567,
        nome_arquivo=f"PEDIDO_{NUMERO}_57107095000164.txt", data_cancelamento=_datetime(2026, 10, 31, 9, 1, 2),
    )

    assert cancelamento_service.gerar_cancelado_closeup(industria, pedido) is True

    _comparar_com_golden(Path(industria.pasta_cancelamento) / f"CANCELAMENTO_{NUMERO}_57107095000164.TXT", "cancelamento.txt")


def test_golden_estoque(monkeypatch, tmp_path):
    monkeypatch.setattr(estoque_service, "datetime", _Agora)
    monkeypatch.setattr(estoque_service, "exigir_cnpj_distribuidor", lambda: CNPJ_DISTRIBUIDOR)
    monkeypatch.setattr(estoque_service, "buscar_fornecedores_industria", lambda id_industria: [10, 20])
    monkeypatch.setattr(estoque_service, "envia_arquivo_para_pasta", lambda *a: None)
    monkeypatch.setattr(estoque_service, "resgata_estoque", lambda fornecedores: pd.DataFrame({
        "Cod_barra": ["7891234567895 ", "789123", "7890000000017"],
        "estoque_disponivel": [150, 0, 12],
    }))
    industria = criar_industria(tmp_path, pasta_estoque=str(tmp_path / "estoque"))

    estoque_service.gerar_estoque_closeup(industria, None)

    _comparar_com_golden(Path(industria.pasta_estoque) / "ESTOQUE_P_HYPERA_CAC.TXT", "estoque.txt")


def _linha_pedido(tamanho: int, campos: dict[int, str]) -> str:
    linha = [" "] * tamanho
    for inicio, valor in campos.items():
        linha[inicio:inicio + len(valor)] = list(valor)
    return "".join(linha)


def test_golden_leitura_do_pedido(monkeypatch, tmp_path):
    cabecalho = _linha_pedido(247, {0: "1", 1: "057107095000164", 16: NUMERO, 86: "ENTREGAR ATE AS 10H. PORTA 2"})
    item1 = _linha_pedido(120, {0: "2", 1: NUMERO, 21: "7891234567895", 34: "00010", 43: "01250", 93: "03692"})
    item2 = _linha_pedido(120, {0: "2", 1: NUMERO, 21: "0000000789123", 34: "00024", 43: "03334"})
    rodape = "3" + NUMERO + "00004"
    arquivo = tmp_path / f"PEDIDO_{NUMERO}_57107095000164.txt"
    arquivo.write_text("\n".join([cabecalho, item1, item2, rodape]) + "\n", encoding="utf-8")
    produtos = {"7891234567895": {"preco": 8.9, "codigo_produto": 101}}
    monkeypatch.setattr(conversor, "resgatar_produto", lambda ean: produtos.get(ean))
    industria = criar_industria(tmp_path, cond_mae=3692)

    pedido = conversor.converter_arquivo_closeup(industria, str(arquivo))

    lido = {
        "nome_arquivo": pedido.nome_arquivo, "cnpj_cliente": pedido.cnpj_cliente,
        "numero_pedido_ol": pedido.numero_pedido_ol, "data_pedido": str(pedido.data_pedido),
        "observacao": pedido.observacao, "id_cond": pedido.id_cond,
        "itens": [
            {c: getattr(i, c) for c in ("numero_pedido_ol", "cnpj_cliente", "ean", "quantidade_solicitada",
                                        "desconto", "id_cond", "preco", "quantidade_atendida", "codigo_produto")}
            for i in pedido.itens
        ],
    }
    golden = GOLDEN / "pedido_lido.json"
    if ATUALIZAR:
        golden.write_text(json.dumps(lido, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    assert lido == json.loads(golden.read_text(encoding="utf-8"))
