"""
Fixtures e funções auxiliares compartilhadas pelos testes do OL_CORE.

Convenção usada nestes testes
------------------------------
Os validators/services do OL_CORE importam as funções de banco (MySQL/SQL
Server) e de FTP diretamente dentro de cada módulo, por exemplo:

    from ol_core.database.sqlserver.contexto_cliente import resgatar_cliente

Por isso, para "trocar" o retorno dessas funções nos testes, sempre usamos
`monkeypatch.setattr` apontando para o módulo QUE CHAMA a função (ex.:
`valida_cliente.resgatar_cliente`), nunca para o módulo onde ela foi
originalmente definida (`contexto_cliente.resgatar_cliente`). O Python já
"copiou" a referência da função pro módulo que fez o import — trocar só no
módulo original não afeta quem já importou.

Nenhum teste aqui deve tocar o MySQL, o SQL Server (ERP) ou o FTP de verdade.
"""
from datetime import datetime, timedelta

# O ol_core vem instalado no venv (`pip install -e OL_CORE`, ver
# requirements-test.txt) — não há mais sys.path apontando para a pasta.
from ol_core.models.pedido import Pedido
from ol_core.models.pedido_item import Pedido_Item
from ol_core.models.industria import Industria
from ol_core.models.titulo import Titulo
from ol_core.models.titulo_item import Titulo_Item
from ol_core.models.enums.tipo_layout import TipoLayout


def criar_pedido(**dados) -> Pedido:
    """Cria um Pedido de teste com valores padrão razoáveis.
    Sobrescreva só os campos que o teste realmente precisa."""
    padrao = dict(
        numero_pedido_ol="00000000000000000001",
        cnpj_cliente="12345678000199",
        codigo_interno_pedido=100,
        valor_total=500.0,
        cod_situacao=0,
    )
    padrao.update(dados)
    return Pedido(**padrao)


def criar_item(**dados) -> Pedido_Item:
    """Cria um Pedido_Item de teste com valores padrão razoáveis."""
    padrao = dict(
        numero_pedido_ol="00000000000000000001",
        cnpj_cliente="12345678000199",
        codigo_produto=999,
        ean="7890000000001",
        quantidade_solicitada=10,
        quantidade_atendida=10,
        preco=10.0,
        desconto=0.0,
        condicao="123",
        id_cond=123,
        cod_motivo=0,
    )
    padrao.update(dados)
    return Pedido_Item(**padrao)


def criar_industria(tmp_path, **dados) -> Industria:
    """
    Cria uma Industria de teste com todas as pastas apontando para dentro de
    tmp_path (pasta temporária do próprio pytest, apagada ao final do teste)
    — assim nenhum teste cria diretório de verdade dentro do repositório.
    """
    padrao = dict(
        id_industria=1,
        nome="Industria Teste",
        tipo_layout=TipoLayout.CLOSEUP,
        cond_mae=3692,
        pasta_retorno=str(tmp_path / "retorno"),
        pasta_envio_retorno=str(tmp_path / "envio_retorno"),
        pasta_nfe=str(tmp_path / "nfe"),
        pasta_envio_nf=str(tmp_path / "envio_nf"),
        pasta_cancelamento=str(tmp_path / "cancelamento"),
        pasta_envio_cancelamento=str(tmp_path / "envio_cancelamento"),
        pasta_erro=str(tmp_path / "erro"),
    )
    padrao.update(dados)
    return Industria(**padrao)


def criar_titulo(**dados) -> Titulo:
    """Cria um Titulo de teste (usado nos testes do espelho_service)."""
    padrao = dict(
        codigo_pedido_interno=100,
        nome_arquivo="PEDIDO_00000000000000000001_12345678000199.txt",
        cnpj_cliente="12345678000199",
        numero_pedido_ol="00000000000000000001",
        data_emissao=datetime.now(),
        data_vencimento=datetime.now() + timedelta(days=30),
        codigo_titulo=1,
        numero_titulo="1",
        serie_nf=1,
        codigo_situacao=0,
        data_cancelamento=None,
        quem_cancelou=None,
        chave_acesso="",
    )
    padrao.update(dados)
    return Titulo(**padrao)


def criar_titulo_item(**dados) -> Titulo_Item:
    """Cria um Titulo_Item de teste (usado nos testes do espelho_service)."""
    padrao = dict(
        codigo_produto=999,
        ean="7890000000001",
        quantidade_atendida=10,
        desconto=0.0,
        prazo=30,
        quantidade_solicitada=10,
        produtos_motivo=0,
        preco=10.0,
    )
    padrao.update(dados)
    return Titulo_Item(**padrao)


import pytest


@pytest.fixture(autouse=True)
def _parametros_desligados_por_padrao(request, monkeypatch):
    """Isola os testes do MySQL real: sem isso `parametro_esta_ativo` lê a tabela de
    parâmetros e as ocorrências viram IGNORADO conforme o ambiente. Testes que
    precisam do parâmetro ligado seguem patchando `parametro_esta_ativo` no validador."""
    if request.module.__name__.endswith("test_contexto_parametros"):
        return
    from ol_core.database.mysql import contexto_parametros
    monkeypatch.setattr(contexto_parametros, "obter_valor_parametro", lambda chave, *a, **k: None)
