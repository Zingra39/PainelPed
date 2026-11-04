"""Testes de ol_core.services.import_service.LayouFactory — foco na task 30
(separação entre registrar e validar pedido) e no que foi encontrado em
validações sucessivas dessa correção.

Histórico relevante:
- LayouFactory.validar_pedido() (que existia como método próprio, com seu
  try/except em volta do laço de itens) foi removida. import_service.py
  agora chama direto a função valida_pedido() de
  ol_core.validators.valida_pedido — que ficou responsável por orquestrar
  valida_clientes + valida_valor_total_pedido + valida_produto, com sua
  própria rede de segurança (registra ocorrência ERRO se algo escapar).
  Essa parte é coberta em test_valida_pedido.py.
- A isolação de itens dentro do laço de validação de produtos também
  mudou de lugar: hoje mora dentro de valida_produto() (que recebe o
  pedido inteiro de uma vez), coberta em test_valida_produto.py.
- reprocessar() ainda tem um bug de chamada a valida_produto() — só que
  mudou de tipo de erro (ver teste no fim deste arquivo).
"""
from contextlib import contextmanager
from pathlib import Path

import pytest

from ol_core.core.exceptions import ErroConexaoBanco
from ol_core.services import import_service
from ol_core.layouts import closeup as layout_closeup  # a leitura do pedido CloseUp passa pelo layout registrado
from ol_core.services.import_service import LayouFactory
from ol_core.models.enums.tipo_status_oper import TipoStatusOper
from .conftest import criar_industria, criar_item, criar_pedido


class _TransacaoFalsa:
    """Substitui ol_core.core.conexao.transacao: registra se a transação
    terminou em COMMIT ou ROLLBACK, sem banco."""

    def __init__(self):
        self.desfechos: list[str] = []

    @contextmanager
    def __call__(self):
        try:
            yield None
        except BaseException:
            self.desfechos.append("rollback")
            raise
        self.desfechos.append("commit")


@pytest.fixture(autouse=True)
def transacao_falsa(monkeypatch):
    falsa = _TransacaoFalsa()
    monkeypatch.setattr(import_service, "transacao", falsa)
    return falsa


# --------------------------------------------------------------------- registra_pedido (task 30)

def test_registra_pedido_retorna_id_arquivo_quando_tudo_da_certo(monkeypatch):
    monkeypatch.setattr(import_service, "inserir_pedido", lambda id_industria, pedido: 1)
    monkeypatch.setattr(import_service, "inserir_pedido_itens", lambda itens: 1)
    monkeypatch.setattr(import_service, "registrar_arquivo", lambda arquivo, situacao: 1)
    monkeypatch.setattr(import_service, "verifica_quantidade_que_sera_atendida", lambda codigo_produto: None)

    pedido = criar_pedido()
    pedido.itens = [criar_item()]

    resultado = LayouFactory.registra_pedido(pedido, id_industria=1, arquivo="PEDIDO_TESTE.txt")

    assert resultado == 1


def test_registra_pedido_retorna_none_quando_inserir_pedido_falha(monkeypatch):
    monkeypatch.setattr(import_service, "inserir_pedido", lambda id_industria, pedido: None)
    monkeypatch.setattr(import_service, "verifica_quantidade_que_sera_atendida", lambda codigo_produto: None)

    pedido = criar_pedido()
    pedido.itens = [criar_item()]

    resultado = LayouFactory.registra_pedido(pedido, id_industria=1, arquivo="PEDIDO_TESTE.txt")

    assert resultado is None


def test_registra_pedido_desfaz_o_pedido_quando_os_itens_falham(monkeypatch, transacao_falsa):
    # Item 2/A3: pedido, itens e arquivo numa transação só — itens falharam,
    # o pedido já inserido não pode ficar gravado sozinho.
    monkeypatch.setattr(import_service, "inserir_pedido", lambda id_industria, pedido: 1)
    monkeypatch.setattr(import_service, "inserir_pedido_itens", lambda itens: None)
    chamou_arquivo = []
    monkeypatch.setattr(import_service, "registrar_arquivo", lambda a, s: chamou_arquivo.append(True) or 1)
    monkeypatch.setattr(import_service, "verifica_quantidade_que_sera_atendida", lambda codigo_produto: None)

    pedido = criar_pedido()
    pedido.itens = [criar_item()]

    assert LayouFactory.registra_pedido(pedido, id_industria=1, arquivo="PEDIDO_TESTE.txt") is None
    assert transacao_falsa.desfechos == ["rollback"]
    assert chamou_arquivo == []


def test_registra_pedido_grava_tudo_num_unico_commit(monkeypatch, transacao_falsa):
    monkeypatch.setattr(import_service, "inserir_pedido", lambda id_industria, pedido: 1)
    monkeypatch.setattr(import_service, "inserir_pedido_itens", lambda itens: 1)
    monkeypatch.setattr(import_service, "registrar_arquivo", lambda arquivo, situacao: 7)
    monkeypatch.setattr(import_service, "verifica_quantidade_que_sera_atendida", lambda codigo_produto: None)

    pedido = criar_pedido()
    pedido.itens = [criar_item()]

    assert LayouFactory.registra_pedido(pedido, id_industria=1, arquivo="PEDIDO_TESTE.txt") == 7
    assert transacao_falsa.desfechos == ["commit"]


# --------------------------------------------------------------------- importar (task 30)

def test_importar_nao_chama_valida_pedido_quando_registro_falha(monkeypatch, tmp_path):
    # Este é o núcleo da correção da task 30: se o pedido não foi
    # persistido, não faz sentido gerar ocorrências de validação pra ele.
    industria = criar_industria(tmp_path)
    pedido = criar_pedido()
    pedido.itens = [criar_item()]

    chamou_validar = []
    monkeypatch.setattr(LayouFactory, "registra_pedido", staticmethod(lambda p, i, a: False))
    monkeypatch.setattr(import_service, "valida_pedido", lambda p, c: chamou_validar.append(True))
    monkeypatch.setattr(layout_closeup, "converter_arquivo_closeup", lambda industria, arquivo: pedido)

    resultado = LayouFactory.importar(industria, "PEDIDO_TESTE.txt")

    assert chamou_validar == []
    # A4: importar() avisa que falhou, para o script NÃO mover o arquivo.
    assert resultado is False


def test_importar_chama_valida_pedido_quando_registro_da_certo(monkeypatch, tmp_path):
    industria = criar_industria(tmp_path)
    pedido = criar_pedido()
    pedido.itens = [criar_item()]

    chamou_validar = []
    monkeypatch.setattr(LayouFactory, "registra_pedido", staticmethod(lambda p, i, a: True))
    monkeypatch.setattr(import_service, "valida_pedido", lambda p, c: chamou_validar.append(True))
    monkeypatch.setattr(layout_closeup, "converter_arquivo_closeup", lambda industria, arquivo: pedido)
    monkeypatch.setattr(import_service, "buscar_ocorrencias_nao_resolvidas", lambda numero: [])
    monkeypatch.setattr(import_service, "atualizar_status_pedido", lambda numero, status: None)
    monkeypatch.setattr(import_service, "atualizar_situacao_arquivo", lambda id_arquivo, situacao: None)
    monkeypatch.setattr(import_service, "parametro_esta_ativo", lambda chave: False)

    resultado = LayouFactory.importar(industria, "PEDIDO_TESTE.txt")

    assert chamou_validar == [True]
    assert resultado is True


def test_importar_desfaz_tudo_se_a_validacao_quebra_no_meio(monkeypatch, tmp_path, transacao_falsa):
    industria = criar_industria(tmp_path)
    pedido = criar_pedido()
    monkeypatch.setattr(LayouFactory, "registra_pedido", staticmethod(lambda p, i, a: 1))
    monkeypatch.setattr(layout_closeup, "converter_arquivo_closeup", lambda industria, arquivo: pedido)

    def validacao_quebra(p, c):
        raise ValueError("erro inesperado")

    monkeypatch.setattr(import_service, "valida_pedido", validacao_quebra)

    assert LayouFactory.importar(industria, "PEDIDO_TESTE.txt") is False
    assert transacao_falsa.desfechos == ["rollback"]


def test_importar_propaga_queda_do_banco_para_o_script_interromper_o_lote(monkeypatch, tmp_path, transacao_falsa):
    industria = criar_industria(tmp_path)
    pedido = criar_pedido()
    monkeypatch.setattr(layout_closeup, "converter_arquivo_closeup", lambda industria, arquivo: pedido)

    def banco_caiu(p, i, a):
        raise ErroConexaoBanco("MySQL", "2003 Can't connect")

    monkeypatch.setattr(LayouFactory, "registra_pedido", staticmethod(banco_caiu))

    with pytest.raises(ErroConexaoBanco):
        LayouFactory.importar(industria, "PEDIDO_TESTE.txt")
    assert transacao_falsa.desfechos == ["rollback"]


# --------------------------------------------------------------------- reprocessar

def test_reprocessar_com_pedido_com_itens_deveria_validar_sem_erro(monkeypatch, tmp_path):
    industria = criar_industria(tmp_path)
    pedido = criar_pedido()
    pedido.itens = [criar_item()]

    monkeypatch.setattr(import_service, "marcar_ocorrencias_resolvidas", lambda numero_pedido_ol: None)
    monkeypatch.setattr(layout_closeup, "converter_arquivo_closeup", lambda industria, arquivo: pedido)
    monkeypatch.setattr(import_service, "valida_pedido", lambda pedido, cond: None)
    monkeypatch.setattr(import_service, "atualizar_valor_total_pedido", lambda numero_pedido_ol, valor: None)
    monkeypatch.setattr(import_service, "buscar_ocorrencias_nao_resolvidas", lambda numero_pedido_ol: [])
    monkeypatch.setattr(import_service, "atualizar_status_pedido", lambda numero_pedido_ol, status: None)
    monkeypatch.setattr(import_service, "verifica_quantidade_que_sera_atendida", lambda codigo_produto: None)

    resultado, _mensagem = LayouFactory.reprocessar(industria, pedido, Path("PEDIDO_TESTE.txt"))

    assert resultado is True


# B6 da auditoria: resolver ocorrências antigas, recalcular valor, validar e
# mudar status acontecem numa única transação.

def _stub_reprocessar(monkeypatch, pedido, pendencias=(), valida=None):
    """Registra a ordem das gravações do reprocessamento, sem banco."""
    chamadas: list[str] = []
    # calcula_valor_total consulta o ERP (quantidade atendida) antes da transação.
    monkeypatch.setattr(import_service, "verifica_quantidade_que_sera_atendida", lambda codigo_produto: None)
    monkeypatch.setattr(layout_closeup, "converter_arquivo_closeup", lambda industria, arquivo: pedido)
    monkeypatch.setattr(import_service, "marcar_ocorrencias_resolvidas", lambda numero: chamadas.append("resolver"))
    monkeypatch.setattr(import_service, "atualizar_valor_total_pedido", lambda numero, valor: chamadas.append("valor"))
    monkeypatch.setattr(import_service, "valida_pedido", valida or (lambda p, cond: chamadas.append("validar")))
    monkeypatch.setattr(import_service, "buscar_ocorrencias_nao_resolvidas", lambda numero: list(pendencias))
    monkeypatch.setattr(import_service, "atualizar_status_pedido", lambda numero, status: chamadas.append(status))
    return chamadas


def test_reprocessar_grava_tudo_num_unico_commit(monkeypatch, tmp_path, transacao_falsa):
    pedido = criar_pedido()
    pedido.itens = [criar_item()]
    chamadas = _stub_reprocessar(monkeypatch, pedido, pendencias=[{"id": 1}])

    ok, mensagem = LayouFactory.reprocessar(criar_industria(tmp_path), pedido, Path("PEDIDO_TESTE.txt"))

    assert ok is False and "1 ocorrência(s) pendente(s)" in mensagem
    assert chamadas == ["resolver", "valor", "validar", TipoStatusOper.VERIFICAR.value]
    assert transacao_falsa.desfechos == ["commit"]


def test_reprocessar_desfaz_tudo_se_a_validacao_quebra_e_marca_falha(monkeypatch, tmp_path, transacao_falsa):
    """A falha no meio não pode deixar as ocorrências antigas resolvidas sem
    nenhuma nova (rollback), nem o pedido travado em "Reprocessando"."""
    pedido = criar_pedido()
    pedido.itens = [criar_item()]

    def valida_quebra(p, cond):
        raise RuntimeError("ERP indisponível no meio da validação")

    chamadas = _stub_reprocessar(monkeypatch, pedido, valida=valida_quebra)

    ok, mensagem = LayouFactory.reprocessar(criar_industria(tmp_path), pedido, Path("PEDIDO_TESTE.txt"))

    assert ok is False and "ERP indisponível" in mensagem
    assert transacao_falsa.desfechos == ["rollback"]
    # Depois do rollback, só o status de falha é gravado (fora da transação desfeita).
    assert chamadas[-1] == TipoStatusOper.FALHA_REPROCESSAMENTO.value


def test_reprocessar_sem_conseguir_ler_o_arquivo_nao_mexe_nas_ocorrencias(monkeypatch, tmp_path, transacao_falsa):
    pedido = criar_pedido()
    chamadas = _stub_reprocessar(monkeypatch, None)

    ok, _ = LayouFactory.reprocessar(criar_industria(tmp_path), pedido, Path("PEDIDO_TESTE.txt"))

    assert ok is False
    assert "resolver" not in chamadas
    assert transacao_falsa.desfechos == []
    assert chamadas == [TipoStatusOper.FALHA_REPROCESSAMENTO.value]


def test_reprocessar_propaga_queda_do_banco(monkeypatch, tmp_path, transacao_falsa):
    pedido = criar_pedido()
    pedido.itens = [criar_item()]

    def valida_banco_caiu(p, cond):
        raise ErroConexaoBanco("MySQL", "conexão perdida")

    _stub_reprocessar(monkeypatch, pedido, valida=valida_banco_caiu)

    with pytest.raises(ErroConexaoBanco):
        LayouFactory.reprocessar(criar_industria(tmp_path), pedido, Path("PEDIDO_TESTE.txt"))
    assert transacao_falsa.desfechos == ["rollback"]


# --------------------------------------------------------------------- transmissão automática
# (parâmetro `transmissao_automatica_pronto` — Card de parametrização,
# squad review 2026-09-17)

def _stub_transmissao_infra(monkeypatch):
    """Isola importar()/_transmitir_automaticamente do banco de verdade,
    registrando as chamadas de status e histórico numa lista pra os testes
    inspecionarem, igual ao padrão já usado em OL_TEST/api/test_operacoes_retorno.py."""
    status_chamados: list[str] = []
    historico_chamados: list[dict] = []

    monkeypatch.setattr(
        import_service, "atualizar_status_pedido",
        lambda numero_pedido_ol, status: status_chamados.append(status),
    )
    monkeypatch.setattr(
        import_service, "registrar_historico",
        lambda numero_pedido_ol, acao, detalhe, id_usuario: historico_chamados.append(
            {"acao": acao, "detalhe": detalhe, "id_usuario": id_usuario}
        ),
    )
    monkeypatch.setattr(import_service, "obter_id_usuario_sistema", lambda: 99)
    # Acrescentados quando a transmissão passou a gravar status ERP e transmitido_em:
    # sem estes stubs o teste tenta conectar ao MySQL real.
    monkeypatch.setattr(import_service, "atualizar_status_erp_pedido", lambda numero, status: None)
    monkeypatch.setattr(import_service, "atualizar_transmitido_em", lambda numero: None)
    return status_chamados, historico_chamados


def _stub_importar_ate_o_branch_de_status(monkeypatch, pedido, pendencias, parametro_ativo):
    """Deixa importar() chegar até o if/elif/else de status sem depender de
    parsing de arquivo, validação de pedido, nem registro real no banco."""
    monkeypatch.setattr(LayouFactory, "registra_pedido", staticmethod(lambda p, i, a: 1))
    monkeypatch.setattr(import_service, "valida_pedido", lambda p, c: None)
    monkeypatch.setattr(layout_closeup, "converter_arquivo_closeup", lambda industria, arquivo: pedido)
    monkeypatch.setattr(import_service, "buscar_ocorrencias_nao_resolvidas", lambda numero: pendencias)
    monkeypatch.setattr(import_service, "parametro_esta_ativo", lambda chave: parametro_ativo)
    monkeypatch.setattr(import_service, "atualizar_situacao_arquivo", lambda id_arquivo, situacao: None)


def test_importar_com_parametro_desligado_mantem_comportamento_atual_pronto(monkeypatch, tmp_path):
    # Comportamento padrão (parâmetro nunca foi ligado, ou foi desligado
    # explicitamente): nada muda — pedido fica "Pronto" na fila de triagem.
    industria = criar_industria(tmp_path)
    pedido = criar_pedido()
    status_chamados, _historico = _stub_transmissao_infra(monkeypatch)
    _stub_importar_ate_o_branch_de_status(monkeypatch, pedido, pendencias=[], parametro_ativo=False)

    chamou_transmissao = []
    monkeypatch.setattr(
        LayouFactory, "_transmitir_automaticamente",
        staticmethod(lambda p, i, a: chamou_transmissao.append(True)),
    )

    LayouFactory.importar(industria, "PEDIDO_TESTE.txt")

    assert status_chamados == [TipoStatusOper.PRONTO.value]
    assert chamou_transmissao == []


def test_importar_com_parametro_ligado_chama_transmissao_automatica_em_vez_de_pronto(monkeypatch, tmp_path):
    industria = criar_industria(tmp_path)
    pedido = criar_pedido()
    status_chamados, _historico = _stub_transmissao_infra(monkeypatch)
    _stub_importar_ate_o_branch_de_status(monkeypatch, pedido, pendencias=[], parametro_ativo=True)

    chamou_transmissao = []
    monkeypatch.setattr(
        LayouFactory, "_transmitir_automaticamente",
        staticmethod(lambda p, i, a: chamou_transmissao.append(True)),
    )

    LayouFactory.importar(industria, "PEDIDO_TESTE.txt")

    # O pedido é gravado como "Pronto" dentro da transação do registro e só
    # DEPOIS do commit a transmissão automática (cópia de arquivo, que rollback
    # não desfaz) leva para Transmitindo/Transmitido. Se ela falhar ou o
    # processo cair no meio, o pedido já está na fila de triagem.
    assert status_chamados == [TipoStatusOper.PRONTO.value]
    assert chamou_transmissao == [True]


def test_importar_com_pendencias_ignora_parametro_ligado_e_vai_para_verificar(monkeypatch, tmp_path):
    # Pendência de validação tem prioridade sobre o parâmetro: um pedido com
    # ocorrência não pode ser transmitido automaticamente de jeito nenhum.
    industria = criar_industria(tmp_path)
    pedido = criar_pedido()
    status_chamados, _historico = _stub_transmissao_infra(monkeypatch)
    _stub_importar_ate_o_branch_de_status(monkeypatch, pedido, pendencias=[{"id": 1}], parametro_ativo=True)

    chamou_transmissao = []
    monkeypatch.setattr(
        LayouFactory, "_transmitir_automaticamente",
        staticmethod(lambda p, i, a: chamou_transmissao.append(True)),
    )

    LayouFactory.importar(industria, "PEDIDO_TESTE.txt")

    assert status_chamados == [TipoStatusOper.VERIFICAR.value]
    assert chamou_transmissao == []


# --------------------------------------------------------------------- LayouFactory._transmitir_automaticamente

def test_transmitir_automaticamente_com_sucesso_copia_arquivo_e_marca_transmitido(monkeypatch, tmp_path):
    industria = criar_industria(tmp_path, pasta_entrada=str(tmp_path / "entrada"))
    pedido = criar_pedido()  # observacao=None por padrão (conftest não sobrescreve)

    origem = tmp_path / "PEDIDO_TESTE.txt"
    origem.write_text("1" + "A" * 250, encoding="utf-8")

    status_chamados, historico_chamados = _stub_transmissao_infra(monkeypatch)

    LayouFactory._transmitir_automaticamente(pedido, industria, str(origem))

    assert status_chamados == [TipoStatusOper.TRANSMITINDO.value, TipoStatusOper.TRANSMITIDO.value]
    destino = industria.pasta_entrada / "PEDIDO_TESTE.txt"
    assert destino.exists()
    assert destino.read_text(encoding="utf-8") == origem.read_text(encoding="utf-8")
    assert historico_chamados[-1]["acao"] == "Arquivo transmitido"
    assert historico_chamados[-1]["id_usuario"] == 99


def test_transmitir_automaticamente_sem_pasta_entrada_configurada_reverte_para_pronto(monkeypatch, tmp_path):
    # criar_industria() sem override deixa pasta_entrada=None (não configurada).
    industria = criar_industria(tmp_path)
    pedido = criar_pedido()

    status_chamados, historico_chamados = _stub_transmissao_infra(monkeypatch)

    LayouFactory._transmitir_automaticamente(pedido, industria, str(tmp_path / "PEDIDO_TESTE.txt"))

    assert status_chamados == [TipoStatusOper.TRANSMITINDO.value, TipoStatusOper.PRONTO.value]
    assert historico_chamados[-1]["acao"] == "Falha na transmissão automática"
    assert historico_chamados[-1]["id_usuario"] == 99


def test_transmitir_automaticamente_com_arquivo_origem_ausente_reverte_para_pronto(monkeypatch, tmp_path):
    # Pasta de entrada configurada, mas o arquivo de origem não existe em
    # disco (simula qualquer falha de I/O na cópia) — nunca deve deixar o
    # pedido travado em "Transmitindo".
    industria = criar_industria(tmp_path, pasta_entrada=str(tmp_path / "entrada"))
    pedido = criar_pedido()

    status_chamados, historico_chamados = _stub_transmissao_infra(monkeypatch)

    LayouFactory._transmitir_automaticamente(pedido, industria, str(tmp_path / "NAO_EXISTE.txt"))

    assert status_chamados == [TipoStatusOper.TRANSMITINDO.value, TipoStatusOper.PRONTO.value]
    assert historico_chamados[-1]["acao"] == "Falha na transmissão automática"
