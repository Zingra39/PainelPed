"""Testes de ol_core.services.retorno_service.

Cobre verificar_itens_pedido (merge de itens) e gerar_retorno_closeup
(geracao do arquivo de retorno). Toda consulta a banco/FTP e trocada por
monkeypatch — nenhum teste aqui toca infraestrutura de verdade.

Arquitetura atual de verificar_itens_pedido (reescrita apos a task
"validar merge de itens do retorno"):

    1. Busca os itens no SQL Server (ERP) via
       verifica_todos_eans_itens_pedido_pelo_nome_arquivo — pode devolver
       mais de uma linha por item de pedido, porque o JOIN com
       caixa_fechada nao filtra "principal = -1" (ao contrario das
       funcoes irmas): um produto com mais de uma embalagem cadastrada
       gera uma linha por EAN de embalagem.
    2. Busca os itens no MySQL (banco operacional, o que foi realmente
       importado do arquivo do pedido) via
       verificar_itens_pedido_pelo_nome_arquivo_mysql.
    3. Faz a INTERSECAO dos dois por EAN (chave trocada de codigo_produto
       para ean nesta task — codigo_produto tinha um bug de colisao,
       porque produtos nao cadastrados caem no fallback codigo_produto=0
       e passavam a ser tratados como "o mesmo produto" entre si).
       Para os EANs em comum, fica a versao do SQL Server (mais
       atualizada/oficial).
    4. Insere, alem disso, os itens que existem no MySQL mas nao entraram
       na intersecao (itens "faltantes" do MySQL). Itens que existem so
       no SQL Server (nao foram registrados no MySQL) ficam de fora.

IMPORTANTE — bug corrigido nesta task (retorno com item nao cadastrado no
Delage): quando UMA das duas fontes nao tem NENHUM item pro pedido (mais
comum: Delage sem item porque o produto nao esta cadastrado la — ver pedido
2026091000328692172P), a funcao ja tinha a logica de merge pronta (passo 3/4
acima) mas nunca chegava nela — um "if fonte_a is None or fonte_b is None:
return []" no topo descartava a lista inteira, mesmo quando a OUTRA fonte
tinha os itens completos. Agora, quando so uma fonte esta vazia, usa
integralmente a outra; lista vazia so quando as duas estao vazias.

IMPORTANTE — bug corrigido nesta task (ver README.md): dentro de
gerar_retorno_closeup, o bloco "except" referenciava a variavel id_arquivo
(e numero_pedido_ol), mas elas so eram definidas no meio do "try" — uma
excecao antes disso quebrava o proprio tratamento de erro com
UnboundLocalError em vez de devolver False. Corrigido inicializando as
duas como None antes do try (ver
test_erro_real_antes_de_id_arquivo_ser_definido_deveria_retornar_false_sem_quebrar).
"""
from pathlib import Path

import pytest

from ol_core.services import retorno_service
from ol_core.models.enums.tipo_status_erp import TipoStatusErp
from ol_core.models.enums.tipo_status_oper import TipoStatusOper
from .conftest import criar_industria, criar_pedido, criar_item
from ol_core.validators.validador import valida_motivo as _valida_motivo_real


def _preparar_mocks_de_infraestrutura(monkeypatch, id_arquivo_existente=None):
    # CNPJ do distribuidor vem da tabela `parametro` (tela de Parametrização).
    monkeypatch.setattr(retorno_service, "exigir_cnpj_distribuidor", lambda: "11222333000181")
    """Neutraliza todas as chamadas de banco/FTP/disparo de arquivo usadas
    por gerar_retorno_closeup, deixando so a logica de montagem do arquivo."""
    monkeypatch.setattr(retorno_service, "verificar_retorno_existente", lambda numero_pedido_ol: id_arquivo_existente)
    monkeypatch.setattr(retorno_service, "registrar_arquivo", lambda arquivo, situacao: 1)
    monkeypatch.setattr(retorno_service, "atualizar_situacao_arquivo", lambda id_arquivo, situacao: None)
    monkeypatch.setattr(retorno_service, "atualizar_status_pedido", lambda numero_pedido_ol, status: None)
    monkeypatch.setattr(retorno_service, "atualizar_status_erp_pedido", lambda numero_pedido_ol, status_erp: None)
    monkeypatch.setattr(retorno_service, "envia_arquivo_ftp", lambda pasta_ftp, caminho: None)
    monkeypatch.setattr(retorno_service, "envia_arquivo_para_pasta", lambda origem, destino: None)
    monkeypatch.setattr(retorno_service, "marcar_ocorrencias_resolvidas", lambda numero_pedido_ol: None)
    monkeypatch.setattr(retorno_service, "marcar_ocorrencias_item_resolvidas", lambda numero_pedido_ol: None)
    monkeypatch.setattr(retorno_service, "valida_motivo", lambda item, pedido, cnpj: 0)
    monkeypatch.setattr(retorno_service, "valida_ean", lambda numero_pedido_ol, codigo_produto, ean: ean)


def _mockar_fontes(monkeypatch, itens_sql, itens_mysql):
    """Troca as duas fontes de dados de verificar_itens_pedido pelos
    valores dados (None simula 'sem itens' na fonte)."""
    monkeypatch.setattr(retorno_service, "verifica_todos_eans_itens_pedido_pelo_nome_arquivo", lambda nome: itens_sql)
    monkeypatch.setattr(retorno_service, "verificar_itens_pedido_pelo_nome_arquivo_mysql", lambda nome: itens_mysql)


# ===================================================================
# verificar_itens_pedido — merge SQL Server + MySQL por EAN
# ===================================================================

def test_intersecao_usa_a_versao_do_sql_server_para_itens_em_comum(monkeypatch):
    item_sql = criar_item(ean="ean-comum", codigo_produto=1, preco=99.0)
    item_mysql = criar_item(ean="ean-comum", codigo_produto=1, preco=1.0)
    _mockar_fontes(monkeypatch, itens_sql=[item_sql], itens_mysql=[item_mysql])

    resultado = retorno_service.verificar_itens_pedido("PEDIDO_TESTE.txt")

    assert len(resultado) == 1
    assert resultado[0].preco == 99.0  # veio do SQL Server, nao do MySQL


def test_item_que_so_existe_no_sql_server_e_excluido_do_resultado(monkeypatch):
    item_so_sql = criar_item(ean="ean-so-no-sql")
    item_mysql = criar_item(ean="ean-outro")
    _mockar_fontes(monkeypatch, itens_sql=[item_so_sql], itens_mysql=[item_mysql])

    resultado = retorno_service.verificar_itens_pedido("PEDIDO_TESTE.txt")

    eans = [i.ean for i in resultado]
    assert "ean-so-no-sql" not in eans
    assert "ean-outro" in eans


def test_item_que_so_existe_no_mysql_e_inserido_no_resultado(monkeypatch):
    item_comum = criar_item(ean="ean-comum")
    item_so_mysql = criar_item(ean="ean-so-no-mysql")
    _mockar_fontes(monkeypatch, itens_sql=[item_comum], itens_mysql=[item_comum, item_so_mysql])

    resultado = retorno_service.verificar_itens_pedido("PEDIDO_TESTE.txt")

    eans = [i.ean for i in resultado]
    assert "ean-comum" in eans
    assert "ean-so-no-mysql" in eans
    assert len(resultado) == 2


def test_dois_itens_com_codigo_produto_zero_e_ean_diferente_nao_colidem_mais(monkeypatch):
    # Regressao: antes da troca da chave de merge pra EAN, dois produtos
    # DIFERENTES que caiam no fallback codigo_produto=0 (produto nao
    # cadastrado no Delage) eram tratados como "o mesmo produto" e um dos
    # dois era perdido no merge. Com EAN como chave isso nao acontece mais.
    item_ancora_sql = criar_item(ean="ean-ancora", codigo_produto=5)
    item_produto_a = criar_item(ean="ean-produto-nao-cadastrado-a", codigo_produto=0)
    item_produto_b = criar_item(ean="ean-produto-nao-cadastrado-b", codigo_produto=0)
    _mockar_fontes(monkeypatch, itens_sql=[item_ancora_sql], itens_mysql=[item_produto_a, item_produto_b])

    resultado = retorno_service.verificar_itens_pedido("PEDIDO_TESTE.txt")

    eans = [i.ean for i in resultado]
    assert "ean-produto-nao-cadastrado-a" in eans
    assert "ean-produto-nao-cadastrado-b" in eans
    assert len(resultado) == 2


def test_sql_server_sem_itens_usa_mysql_como_fallback(monkeypatch):
    # Delage sem NENHUM item pro pedido (produto nao cadastrado la, por
    # exemplo) — usa integralmente os itens do MySQL em vez de devolver [].
    item_mysql = criar_item(ean="ean-so-no-mysql")
    _mockar_fontes(monkeypatch, itens_sql=None, itens_mysql=[item_mysql])

    resultado = retorno_service.verificar_itens_pedido("PEDIDO_TESTE.txt")

    assert resultado == [item_mysql]


def test_mysql_sem_itens_usa_sql_server_como_fallback(monkeypatch):
    item_sql = criar_item(ean="ean-so-no-sql")
    _mockar_fontes(monkeypatch, itens_sql=[item_sql], itens_mysql=None)

    resultado = retorno_service.verificar_itens_pedido("PEDIDO_TESTE.txt")

    assert resultado == [item_sql]


def test_ambas_fontes_sem_itens_retorna_lista_vazia(monkeypatch):
    _mockar_fontes(monkeypatch, itens_sql=None, itens_mysql=None)

    resultado = retorno_service.verificar_itens_pedido("PEDIDO_TESTE.txt")

    assert resultado == []


def test_excecao_durante_a_consulta_retorna_lista_vazia_sem_quebrar(monkeypatch):
    def levanta_erro(nome_pedido):
        raise RuntimeError("falha simulada de conexão com o ERP")

    monkeypatch.setattr(retorno_service, "verifica_todos_eans_itens_pedido_pelo_nome_arquivo", levanta_erro)
    monkeypatch.setattr(retorno_service, "verificar_itens_pedido_pelo_nome_arquivo_mysql", lambda nome: [criar_item()])

    resultado = retorno_service.verificar_itens_pedido("PEDIDO_TESTE.txt")

    assert resultado == []


def test_multiplas_embalagens_do_mesmo_produto_no_sql_server_nao_duplicam_a_quantidade(monkeypatch):
    # verifica_todos_eans_itens_pedido_pelo_nome_arquivo faz JOIN com
    # caixa_fechada sem filtrar "principal = -1" — um produto com mais de
    # uma embalagem cadastrada (ex.: unidade + caixa fechada) pode voltar
    # como 2 linhas para o MESMO item de pedido, cada uma com um EAN de
    # embalagem diferente, mas repetindo a mesma quantidade.
    linha_embalagem_unidade = criar_item(ean="7890000000010", codigo_produto=99, quantidade_atendida=10, quantidade_solicitada=10)
    linha_embalagem_caixa = criar_item(ean="7890000000010999", codigo_produto=99, quantidade_atendida=10, quantidade_solicitada=10)
    # No MySQL so existe UMA linha pra esse item — o EAN que veio no arquivo original do pedido
    item_mysql = criar_item(ean="7890000000010", codigo_produto=99, quantidade_atendida=10, quantidade_solicitada=10)

    _mockar_fontes(
        monkeypatch,
        itens_sql=[linha_embalagem_unidade, linha_embalagem_caixa],
        itens_mysql=[item_mysql],
    )

    resultado = retorno_service.verificar_itens_pedido("PEDIDO_TESTE.txt")

    # so a linha cujo EAN bate exatamente com o EAN gravado no MySQL entra
    # na intersecao — a variante extra de embalagem (que nao existe no
    # MySQL) fica de fora, entao a quantidade nao e contada 2x
    assert len(resultado) == 1
    assert sum(i.quantidade_atendida for i in resultado) == 10


# ===================================================================
# gerar_retorno_closeup — guard clauses
# ===================================================================

def test_gerar_retorno_closeup_sem_codigo_interno_pedido_retorna_false(monkeypatch, tmp_path):
    _preparar_mocks_de_infraestrutura(monkeypatch)
    industria = criar_industria(tmp_path)
    pedido = criar_pedido(codigo_interno_pedido=0)

    resultado = retorno_service.gerar_retorno_closeup(industria, pedido)

    assert resultado is False


def test_gerar_retorno_closeup_sem_codigo_interno_pedido_reflete_falha_na_situacao_do_arquivo(monkeypatch, tmp_path):
    # Bug encontrado nesta task: esta guard clause já marcava o PEDIDO como
    # "Falha no Retorno" (atualizar_status_pedido), mas nunca atualizava a
    # situação do ARQUIVO já registrado (id_arquivo) — que ficava travada em
    # "Retorno Sendo Gerado" pra sempre, mesmo com o pedido em falha.
    _preparar_mocks_de_infraestrutura(monkeypatch)
    chamadas = []
    monkeypatch.setattr(
        retorno_service, "atualizar_situacao_arquivo",
        lambda id_arquivo, situacao: chamadas.append((id_arquivo, situacao)),
    )
    industria = criar_industria(tmp_path)
    pedido = criar_pedido(codigo_interno_pedido=0)

    resultado = retorno_service.gerar_retorno_closeup(industria, pedido)

    assert resultado is False
    assert chamadas == [(1, TipoStatusOper.FALHA_RETORNO.value)]


def test_gerar_retorno_closeup_sem_nome_arquivo_retorna_false(monkeypatch, tmp_path):
    # Guard clause adicionada junto com a correcao desta task: sem
    # nome_arquivo nao da pra buscar os itens em nenhuma das duas fontes.
    _preparar_mocks_de_infraestrutura(monkeypatch)
    industria = criar_industria(tmp_path)
    pedido = criar_pedido(codigo_interno_pedido=100, nome_arquivo=None)

    resultado = retorno_service.gerar_retorno_closeup(industria, pedido)

    assert resultado is False


def test_gerar_retorno_closeup_sem_nome_arquivo_reflete_falha_na_situacao_do_arquivo(monkeypatch, tmp_path):
    _preparar_mocks_de_infraestrutura(monkeypatch)
    chamadas = []
    monkeypatch.setattr(
        retorno_service, "atualizar_situacao_arquivo",
        lambda id_arquivo, situacao: chamadas.append((id_arquivo, situacao)),
    )
    industria = criar_industria(tmp_path)
    pedido = criar_pedido(codigo_interno_pedido=100, nome_arquivo=None)

    resultado = retorno_service.gerar_retorno_closeup(industria, pedido)

    assert resultado is False
    assert chamadas == [(1, TipoStatusOper.FALHA_RETORNO.value)]


def test_gerar_retorno_closeup_sem_itens_retorna_false(monkeypatch, tmp_path):
    # CONFIRMADO CORRIGIDO: antes desta task, gerar_retorno_closeup checava
    # "if pedido_itens is None" — mas verificar_itens_pedido nunca devolve
    # None (so lista, as vezes vazia []), entao essa protecao nunca
    # disparava e o codigo seguia pra gerar um arquivo de retorno vazio.
    # Agora a checagem e "if len(pedido_itens) == 0", que detecta a lista
    # vazia corretamente.
    _preparar_mocks_de_infraestrutura(monkeypatch)
    _mockar_fontes(monkeypatch, itens_sql=None, itens_mysql=None)
    industria = criar_industria(tmp_path)
    pedido = criar_pedido(codigo_interno_pedido=100, nome_arquivo="PEDIDO_TESTE_12345678000199.txt")

    resultado = retorno_service.gerar_retorno_closeup(industria, pedido)

    assert resultado is False


def test_gerar_retorno_closeup_sem_itens_reflete_falha_na_situacao_do_arquivo(monkeypatch, tmp_path):
    _preparar_mocks_de_infraestrutura(monkeypatch)
    chamadas = []
    monkeypatch.setattr(
        retorno_service, "atualizar_situacao_arquivo",
        lambda id_arquivo, situacao: chamadas.append((id_arquivo, situacao)),
    )
    _mockar_fontes(monkeypatch, itens_sql=None, itens_mysql=None)
    industria = criar_industria(tmp_path)
    pedido = criar_pedido(codigo_interno_pedido=100, nome_arquivo="PEDIDO_TESTE_12345678000199.txt")

    resultado = retorno_service.gerar_retorno_closeup(industria, pedido)

    assert resultado is False
    assert chamadas == [(1, TipoStatusOper.FALHA_RETORNO.value)]


def test_gerar_retorno_closeup_sem_pasta_envio_retorno_reflete_falha_na_situacao_do_arquivo(monkeypatch, tmp_path):
    # Mesma classe de bug, guard clause mais tardia: o arquivo de retorno já
    # foi escrito em disco com sucesso, mas a indústria não tem
    # pasta_envio_retorno configurada — não dá pra enviar. A situação do
    # arquivo precisa refletir a falha aqui também, não só o status do pedido.
    _preparar_mocks_de_infraestrutura(monkeypatch)
    chamadas = []
    monkeypatch.setattr(
        retorno_service, "atualizar_situacao_arquivo",
        lambda id_arquivo, situacao: chamadas.append((id_arquivo, situacao)),
    )
    item_comum = criar_item(ean="7890000000001", codigo_produto=1)
    _mockar_fontes(monkeypatch, itens_sql=[item_comum], itens_mysql=[item_comum])

    industria = criar_industria(tmp_path, pasta_envio_retorno=None)
    pedido = criar_pedido(codigo_interno_pedido=100, nome_arquivo="PEDIDO_TESTE_12345678000199.txt")

    resultado = retorno_service.gerar_retorno_closeup(industria, pedido)

    assert resultado is False
    assert chamadas == [(1, TipoStatusOper.FALHA_RETORNO.value)]


def test_gerar_retorno_closeup_com_itens_validos_gera_o_arquivo_com_sucesso(monkeypatch, tmp_path):
    _preparar_mocks_de_infraestrutura(monkeypatch)
    item_comum = criar_item(ean="7890000000001", codigo_produto=1)
    _mockar_fontes(monkeypatch, itens_sql=[item_comum], itens_mysql=[item_comum])

    industria = criar_industria(tmp_path)
    pedido = criar_pedido(codigo_interno_pedido=100, nome_arquivo="PEDIDO_TESTE_12345678000199.txt")

    resultado = retorno_service.gerar_retorno_closeup(industria, pedido)

    assert resultado is True
    arquivos_gerados = list((tmp_path / "retorno").glob("RETORNO_*.TXT"))
    assert len(arquivos_gerados) == 1


def test_gerar_retorno_closeup_com_sucesso_move_status_erp_para_aguardando_faturamento(monkeypatch, tmp_path):
    # Card "usar status_erp de forma mais adequada": ao gerar o Retorno com
    # sucesso, o pedido deve avançar de status_erp (não só status_operacional)
    # para "Aguardando Faturamento" — é esse campo que agora decide se o
    # pedido some da tela de Rastreamento e aparece no Histórico.
    _preparar_mocks_de_infraestrutura(monkeypatch)
    chamadas = []
    monkeypatch.setattr(
        retorno_service, "atualizar_status_erp_pedido",
        lambda numero_pedido_ol, status_erp: chamadas.append((numero_pedido_ol, status_erp)),
    )
    item_comum = criar_item(ean="7890000000001", codigo_produto=1)
    _mockar_fontes(monkeypatch, itens_sql=[item_comum], itens_mysql=[item_comum])

    industria = criar_industria(tmp_path)
    pedido = criar_pedido(codigo_interno_pedido=100, nome_arquivo="PEDIDO_TESTE_12345678000199.txt")

    resultado = retorno_service.gerar_retorno_closeup(industria, pedido)

    assert resultado is True
    assert chamadas == [(pedido.numero_pedido_ol, TipoStatusErp.AGUARDANDO_FATURAMENTO.value)]


def test_erro_antes_de_id_arquivo_ser_definido_deveria_retornar_false_sem_quebrar(monkeypatch, tmp_path):
    _preparar_mocks_de_infraestrutura(monkeypatch)

    def trata_textos_com_falha(*args, **kwargs):
        print(f"Erro ao tratar texto {args}: {kwargs}")
        return "<Error>"

    monkeypatch.setattr(retorno_service, "trata_textos", trata_textos_com_falha)

    industria = criar_industria(tmp_path)
    pedido = criar_pedido(codigo_interno_pedido=100, nome_arquivo="PEDIDO_TESTE_12345678000199.txt")

    resultado = retorno_service.gerar_retorno_closeup(industria, pedido)

    assert resultado is False


def test_erro_real_antes_de_id_arquivo_ser_definido_deveria_retornar_false_sem_quebrar(monkeypatch, tmp_path):
    # Diferente do teste acima (trata_textos devolvendo "<Error>", que faz um
    # "return False" controlado sem nunca chegar no "except"), este forca uma
    # excecao DE VERDADE antes de numero_pedido_ol/id_arquivo serem atribuidos
    # (raise ValueError de "numero do pedido nao informado") — e o cenario que
    # de fato exercitava o UnboundLocalError documentado no topo do arquivo.
    # Com id_arquivo/numero_pedido_ol inicializados como None antes do try,
    # o "except" consegue tratar o erro e devolver False normalmente.
    _preparar_mocks_de_infraestrutura(monkeypatch)
    industria = criar_industria(tmp_path)
    pedido = criar_pedido(numero_pedido_ol=None)

    resultado = retorno_service.gerar_retorno_closeup(industria, pedido)

    assert resultado is False


def test_mesmo_produto_com_ean_diferente_no_sql_e_no_mysql_acata_o_ean_do_mysql(monkeypatch):
    # Regressao do cenario "Neosoro": o mesmo produto pode ter mais de um EAN
    # cadastrado (ex.: embalagem antiga x nova). Se o SQL Server (Delage)
    # devolve o item com um EAN e o MySQL (o que foi de fato registrado no
    # pedido) tem OUTRO EAN para o mesmo produto, sem nenhum EAN em comum
    # entre as duas fontes, o merge por EAN não encontra intersecao — e a
    # regra manda descartar a linha exclusiva do SQL Server e usar a versao
    # do MySQL (unica que sobra), respeitando o que foi realmente pedido.
    item_sql_ean_antigo = criar_item(ean="7894561232569874", codigo_produto=321, preco=99.0)
    item_mysql_ean_novo = criar_item(ean="7896745622178", codigo_produto=321, preco=15.5)
    _mockar_fontes(monkeypatch, itens_sql=[item_sql_ean_antigo], itens_mysql=[item_mysql_ean_novo])

    resultado = retorno_service.verificar_itens_pedido("PEDIDO_TESTE.txt")

    assert len(resultado) == 1
    assert resultado[0].ean == "7896745622178"
    assert resultado[0].preco == 15.5


def test_gerar_retorno_closeup_com_cliente_inexistente_grava_codigo_motivo_221001(monkeypatch, tmp_path):
    # cod_motivo=12 é o atalho do ERP pra "cliente inexistente" — valida_motivo
    # já mapeia isso pra 221001 sem consultar banco (coberto em
    # test_validador.py). Este teste confirma que o código realmente chega
    # até a LINHA do item no arquivo de retorno gerado — a suíte de retorno
    # normalmente mocka valida_motivo pra sempre devolver 0, então usamos a
    # função de verdade aqui pra fechar essa lacuna.
    _preparar_mocks_de_infraestrutura(monkeypatch)
    monkeypatch.setattr(retorno_service, "valida_motivo", _valida_motivo_real)

    item_cliente_inexistente = criar_item(ean="7890000000099", codigo_produto=42, cod_motivo=12)
    _mockar_fontes(monkeypatch, itens_sql=[item_cliente_inexistente], itens_mysql=[item_cliente_inexistente])

    industria = criar_industria(tmp_path)
    pedido = criar_pedido(codigo_interno_pedido=100, nome_arquivo="PEDIDO_TESTE_12345678000199.txt")

    resultado = retorno_service.gerar_retorno_closeup(industria, pedido)

    assert resultado is True
    caminho = Path(industria.pasta_retorno) / f"RETORNO_{pedido.numero_pedido_ol}_{pedido.cnpj_cliente}.TXT"
    linhas_itens = [l for l in caminho.read_text().splitlines() if l.startswith("2")]
    assert len(linhas_itens) == 1
    assert "221001" in linhas_itens[0]


# ===================================================================
# Sincronização da quantidade atendida (Delage -> pedido_item do painel)
# ===================================================================
#
# Na etapa de verificação dos itens, a quantidade atendida que o Delage
# informa (SQL Server, pedido_item.separado) é gravada em
# pedido_item.quantidade_atendida do MySQL, casando por EAN.


@pytest.fixture(autouse=True)
def _sem_escrita_no_mysql(monkeypatch):
    """Rede de segurança: nenhum teste deste arquivo grava no MySQL de verdade."""
    monkeypatch.setattr(retorno_service, "atualizar_quantidade_atendida_itens", lambda *a, **k: 0)


def _gravacoes(monkeypatch):
    chamadas = []
    monkeypatch.setattr(
        retorno_service, "atualizar_quantidade_atendida_itens",
        lambda numero_pedido_ol, quantidades_por_ean: chamadas.append((numero_pedido_ol, dict(quantidades_por_ean))) or len(quantidades_por_ean),
    )
    return chamadas


def test_quantidade_atendida_do_delage_e_gravada_no_mysql_quando_difere(monkeypatch):
    chamadas = _gravacoes(monkeypatch)
    item_sql = criar_item(ean="7890000000001", quantidade_solicitada=10, quantidade_atendida=7)
    item_mysql = criar_item(ean="7890000000001", quantidade_solicitada=10, quantidade_atendida=0)
    _mockar_fontes(monkeypatch, itens_sql=[item_sql], itens_mysql=[item_mysql])

    retorno_service.verificar_itens_pedido("PEDIDO_TESTE.txt")

    assert chamadas == [(item_mysql.numero_pedido_ol, {"7890000000001": 7})]


def test_quantidade_atendida_igual_nao_gera_gravacao(monkeypatch):
    chamadas = _gravacoes(monkeypatch)
    item = criar_item(ean="7890000000001", quantidade_atendida=10)
    _mockar_fontes(monkeypatch, itens_sql=[item], itens_mysql=[criar_item(ean="7890000000001", quantidade_atendida=10)])

    retorno_service.verificar_itens_pedido("PEDIDO_TESTE.txt")

    assert chamadas == []


def test_so_os_itens_que_mudaram_sao_gravados(monkeypatch):
    chamadas = _gravacoes(monkeypatch)
    _mockar_fontes(
        monkeypatch,
        itens_sql=[
            criar_item(ean="7890000000001", quantidade_atendida=10),
            criar_item(ean="7890000000002", quantidade_atendida=3),
        ],
        itens_mysql=[
            criar_item(ean="7890000000001", quantidade_atendida=10),
            criar_item(ean="7890000000002", quantidade_atendida=0),
        ],
    )

    retorno_service.verificar_itens_pedido("PEDIDO_TESTE.txt")

    assert [c[1] for c in chamadas] == [{"7890000000002": 3}]


def test_ean_sem_correspondencia_entre_as_fontes_nao_e_gravado(monkeypatch):
    # Cenário "Neosoro": mesmo produto com EAN diferente no Delage e no MySQL.
    # Sem casamento seguro por EAN, não se grava quantidade.
    chamadas = _gravacoes(monkeypatch)
    _mockar_fontes(
        monkeypatch,
        itens_sql=[criar_item(ean="7894561232569874", codigo_produto=321, quantidade_atendida=5)],
        itens_mysql=[criar_item(ean="7896745622178", codigo_produto=321, quantidade_atendida=0)],
    )

    retorno_service.verificar_itens_pedido("PEDIDO_TESTE.txt")

    assert chamadas == []


def test_ean_com_quantidades_divergentes_no_delage_e_pulado(monkeypatch):
    chamadas = _gravacoes(monkeypatch)
    _mockar_fontes(
        monkeypatch,
        itens_sql=[
            criar_item(ean="7890000000001", quantidade_atendida=4),
            criar_item(ean="7890000000001", quantidade_atendida=6),
        ],
        itens_mysql=[criar_item(ean="7890000000001", quantidade_atendida=0)],
    )

    retorno_service.verificar_itens_pedido("PEDIDO_TESTE.txt")

    assert chamadas == []


def test_delage_sem_itens_nao_sincroniza_nada(monkeypatch):
    chamadas = _gravacoes(monkeypatch)
    _mockar_fontes(monkeypatch, itens_sql=None, itens_mysql=[criar_item(ean="7890000000001", quantidade_atendida=0)])

    resultado = retorno_service.verificar_itens_pedido("PEDIDO_TESTE.txt")

    assert chamadas == []
    assert len(resultado) == 1  # o fallback pro MySQL continua funcionando


def test_falha_na_gravacao_nao_derruba_a_verificacao_dos_itens(monkeypatch):
    def grava_com_erro(numero_pedido_ol, quantidades_por_ean):
        raise RuntimeError("MySQL fora do ar")

    monkeypatch.setattr(retorno_service, "atualizar_quantidade_atendida_itens", grava_com_erro)
    _mockar_fontes(
        monkeypatch,
        itens_sql=[criar_item(ean="7890000000001", quantidade_atendida=7)],
        itens_mysql=[criar_item(ean="7890000000001", quantidade_atendida=0)],
    )

    resultado = retorno_service.verificar_itens_pedido("PEDIDO_TESTE.txt")

    # sem a proteção isso viraria [] e, no retorno, "Falha no Retorno"
    assert len(resultado) == 1
    assert resultado[0].quantidade_atendida == 7


def test_gerar_retorno_closeup_sincroniza_a_quantidade_atendida_e_gera_o_arquivo(monkeypatch, tmp_path):
    _preparar_mocks_de_infraestrutura(monkeypatch)
    chamadas = _gravacoes(monkeypatch)
    _mockar_fontes(
        monkeypatch,
        itens_sql=[criar_item(ean="7890000000001", codigo_produto=1, quantidade_solicitada=10, quantidade_atendida=8)],
        itens_mysql=[criar_item(ean="7890000000001", codigo_produto=1, quantidade_solicitada=10, quantidade_atendida=0)],
    )
    industria = criar_industria(tmp_path)
    pedido = criar_pedido(codigo_interno_pedido=100, nome_arquivo="PEDIDO_TESTE_12345678000199.txt")

    resultado = retorno_service.gerar_retorno_closeup(industria, pedido)

    assert resultado is True
    assert chamadas == [(pedido.numero_pedido_ol, {"7890000000001": 8})]
    caminho = Path(industria.pasta_retorno) / f"RETORNO_{pedido.numero_pedido_ol}_{pedido.cnpj_cliente}.TXT"
    linhas_itens = [l for l in caminho.read_text().splitlines() if l.startswith("2")]
    assert len(linhas_itens) == 1
