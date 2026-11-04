from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey,
    Integer, JSON, String, Text, DECIMAL, UniqueConstraint, text,
)
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.sql.expression import ColumnElement
from sqlalchemy.types import TypeDecorator

from app.core.database import Base


class _AgoraAtualiza(ColumnElement):
    """Default de DDL "agora + atualiza no UPDATE".

    `ON UPDATE CURRENT_TIMESTAMP` só existe no MySQL; em outros dialetos (ex.:
    o SQLite dos testes de API) vira apenas `CURRENT_TIMESTAMP`, e o
    `onupdate=func.now()` da coluna cobre os UPDATEs feitos pelo ORM."""

    inherit_cache = True


@compiles(_AgoraAtualiza)
def _agora_atualiza_padrao(element, compiler, **kw):
    return "CURRENT_TIMESTAMP"


@compiles(_AgoraAtualiza, "mysql")
def _agora_atualiza_mysql(element, compiler, **kw):
    return "CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"


# Defaults que ficam no próprio banco: o OL_CORE insere/atualiza por SQL puro e
# omite estas colunas, então não podem depender de default do lado do Python.
_AGORA = text("CURRENT_TIMESTAMP")
_AGORA_ATUALIZA = _AgoraAtualiza()


class StatusResolvido(TypeDecorator):
    """pedido_ocorrencia.resolvido é VARCHAR(100): "0" (aberta), "1" (resolvida) ou
    "ignorado". Para o restante da API continua bool: só "0" é aberta."""

    impl = String(100)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None or isinstance(value, str):
            return value
        return "1" if value else "0"

    def process_result_value(self, value, dialect):
        return None if value is None else value.strip() != "0"


class Perfil(Base):
    __tablename__ = "perfil"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String(50), unique=True)
    permissoes = Column(JSON)
    criado_em = Column(DateTime, server_default=_AGORA)

    usuarios = relationship("Usuario", back_populates="perfil")


class Usuario(Base):
    __tablename__ = "usuario"

    id = Column(Integer, primary_key=True, autoincrement=True)
    id_perfil = Column(Integer, ForeignKey("perfil.id"))
    nome = Column(String(120))
    email = Column(String(150), unique=True)
    senha_hash = Column(String(255))
    ativo = Column(Boolean, default=True, server_default=text("1"))
    ultimo_acesso = Column(DateTime)
    criado_em = Column(DateTime, server_default=_AGORA)
    atualizado_em = Column(DateTime, server_default=_AGORA_ATUALIZA, onupdate=func.now())

    perfil = relationship("Perfil", back_populates="usuarios")
    historico = relationship("PedidoHistorico", back_populates="usuario")


class Industria(Base):
    __tablename__ = "industria"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String(100))
    cnpj = Column(String(14), unique=True)
    layout = Column("tipo_layout", String(50))
    id_bbs = Column(Integer)
    cond_mae = Column(Integer)
    pasta_envio = Column(String(300))
    pasta_entrada = Column(String(300))
    pasta_retorno = Column(String(300))
    pasta_espelho = Column("pasta_nfe", String(300))
    pasta_cancelamento = Column(String(255))
    pasta_backup_pedido = Column("pasta_backup", String(300))
    pasta_retorno_envio = Column("pasta_envio_retorno", String(300))
    pasta_retorno_espelho = Column("pasta_envio_nf", String(300))
    pasta_pedido_original = Column(String(300))
    pasta_envio_cancelamento = Column(String(255))
    pasta_estoque = Column(String(255))
    ativo = Column(Boolean, default=True, server_default=text("1"))
    criado_em = Column(DateTime, server_default=_AGORA)
    atualizado_em = Column(DateTime, server_default=_AGORA_ATUALIZA, onupdate=func.now())

    pedidos = relationship("Pedido", back_populates="industria")
    ftp = relationship("IndustriaFtp", back_populates="industria", uselist=False, cascade="all, delete-orphan")
    fornecedores = relationship(
        "IndustriaFornecedor", back_populates="industria",
        cascade="all, delete-orphan", order_by="IndustriaFornecedor.cod_fornecedor",
    )


class IndustriaFtp(Base):
    __tablename__ = "industria_ftp"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fk_id_industria = Column(Integer, ForeignKey("industria.id", ondelete="CASCADE"), unique=True)
    ftp_pedidos = Column(String(255))
    ftp_retornos = Column(String(255))
    ftp_espelhos = Column(String(255))
    ftp_cancelados = Column(String(255))
    ftp_estoques = Column(String(255))

    industria = relationship("Industria", back_populates="ftp")


class IndustriaFornecedor(Base):
    """Códigos do fornecedor no ERP do cliente associados à indústria. Filtram
    os produtos do arquivo de estoque (antes fixos no SQL: 10423, 10425, 33929)."""
    __tablename__ = "industria_fornecedor"
    __table_args__ = (
        UniqueConstraint("fk_id_industria", "cod_fornecedor", name="uq_industria_fornecedor"),
        dict(Base.__table_args__),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    fk_id_industria = Column(Integer, ForeignKey("industria.id", ondelete="CASCADE"), nullable=False, index=True)
    cod_fornecedor = Column(Integer, nullable=False)
    descricao = Column(String(100))

    industria = relationship("Industria", back_populates="fornecedores")


class Pedido(Base):
    __tablename__ = "pedido"

    id = Column(Integer, primary_key=True, autoincrement=True)
    numero_pedido_ol = Column(String(50), unique=True)
    id_industria = Column(Integer, ForeignKey("industria.id"))
    nome_arquivo = Column(String(200), unique=True)
    codigo_interno_erp = Column(Integer)
    cnpj_cliente = Column(String(14), index=True)
    condicao = Column(String(255), server_default=text("'0'"))
    id_cond = Column(Integer)
    observacao = Column(String(100))
    data_pedido = Column(DateTime, index=True)
    valor_total = Column(DECIMAL(15, 2))
    status_operacional = Column(String(50), index=True)
    status_erp = Column(String(50), index=True)
    # Momento em que o pedido foi transmitido (copiado para a pasta de entrada
    # da indústria). Base da regra "retorno manual após 1h sem retorno" —
    # `atualizado_em` não serve pra isso, pois muda a cada troca de status.
    transmitido_em = Column(DateTime)
    # Datas de faturamento e de cancelamento do pedido. NULL enquanto o pedido
    # não foi faturado / cancelado (todo pedido nasce sem as duas).
    data_faturamento = Column(DateTime)
    data_cancelamento = Column(DateTime)
    # Motivo real do cancelamento, vindo do ERP (def_situacao.definicao) e
    # gravado por cancelamento_service quando o arquivo de cancelamento é
    # gerado. Não confundir com as ocorrências do pedido: ocorrência é um
    # evento detectado durante o processamento e pode não ter cancelado nada;
    # esta coluna é o motivo pelo qual ESTE pedido foi cancelado.
    motivo_cancelamento = Column(Text)
    # "Em Analise": quem marcou o pedido como em análise na triagem e desde
    # quando. Ambos NULL quando o pedido não está em análise. Quem preenche e
    # limpa é a API (POST/DELETE /pedidos/{id}/analise).
    id_usuario_analise = Column(Integer, ForeignKey("usuario.id"))
    em_analise_desde = Column(DateTime)
    # Selo "Analisado": quem concluiu a análise mais recente do pedido e quando.
    # Diferente das duas colunas acima (que são a TRAVA da análise em curso e
    # voltam a NULL ao encerrar), estas persistem para sempre: são o rastro de
    # que um humano analisou o pedido. Só a API grava, e só quando a análise
    # encerra com sucesso (DELETE /pedidos/{id}/analise); uma nova análise
    # sobrescreve (o selo mostra a última; o histórico completo fica em
    # pedido_historico).
    analisado_por = Column(Integer, ForeignKey("usuario.id"))
    analisado_em = Column(DateTime)
    criado_em = Column(DateTime, server_default=_AGORA)
    atualizado_em = Column(DateTime, server_default=_AGORA_ATUALIZA, onupdate=func.now())
    industria = relationship("Industria", back_populates="pedidos")
    usuario_analise = relationship("Usuario", foreign_keys=[id_usuario_analise])
    usuario_analisou = relationship("Usuario", foreign_keys=[analisado_por])
    itens = relationship("PedidoItem", back_populates="pedido", cascade="all, delete-orphan")
    ocorrencias = relationship("PedidoOcorrencia", back_populates="pedido", cascade="all, delete-orphan")
    arquivos = relationship("Arquivo", back_populates="pedido", cascade="all, delete-orphan")
    historico = relationship("PedidoHistorico", back_populates="pedido", cascade="all, delete-orphan")


class PedidoItem(Base):
    __tablename__ = "pedido_item"

    id = Column(Integer, primary_key=True, autoincrement=True)
    numero_pedido_ol = Column(String(50), ForeignKey("pedido.numero_pedido_ol", ondelete="CASCADE"), index=True)
    ean = Column(String(14), index=True)
    codigo_produto_erp = Column(Integer)
    quantidade_solicitada = Column(Integer)
    quantidade_atendida = Column(Integer)
    preco = Column(DECIMAL(12, 2))
    desconto = Column(DECIMAL(5, 2))
    cod_motivo = Column(Integer)
    status = Column(String(50))
    id_cond = Column(Integer)
    pedido = relationship("Pedido", back_populates="itens")
    ocorrencias = relationship("PedidoItemOcorrencia", back_populates="item", cascade="all, delete-orphan")


class PedidoOcorrencia(Base):
    __tablename__ = "pedido_ocorrencia"

    id = Column(Integer, primary_key=True, autoincrement=True)
    numero_pedido_ol = Column(String(50), ForeignKey("pedido.numero_pedido_ol", ondelete="CASCADE"), index=True)
    severidade = Column(String(50), index=True)
    codigo = Column(String(20))
    descricao = Column(String(500))
    resolvido = Column(StatusResolvido, default=False, server_default=text("'0'"))
    criado_em = Column(DateTime, server_default=_AGORA)

    pedido = relationship("Pedido", back_populates="ocorrencias")


class PedidoItemOcorrencia(Base):
    __tablename__ = "pedido_item_ocorrencia"

    id = Column(Integer, primary_key=True, autoincrement=True)
    id_pedido_item = Column(Integer, ForeignKey("pedido_item.id", ondelete="CASCADE"), index=True)
    severidade = Column(String(50), index=True)
    codigo = Column(String(20))
    descricao = Column(String(500))
    resolvido = Column(Boolean, default=False, server_default=text("0"))
    criado_em = Column(DateTime, server_default=_AGORA)

    item = relationship("PedidoItem", back_populates="ocorrencias")


class Arquivo(Base):
    __tablename__ = "arquivo"

    id = Column(Integer, primary_key=True, autoincrement=True)
    numero_pedido_ol = Column(String(50), ForeignKey("pedido.numero_pedido_ol", ondelete="CASCADE"), index=True)
    nome = Column(String(200))
    tipo = Column(String(50), index=True)
    hash_md5 = Column(String(32))
    caminho = Column(String(500))
    situacao = Column(String(50))
    criado_em = Column(DateTime, server_default=_AGORA)

    pedido = relationship("Pedido", back_populates="arquivos")


class ArquivoBaixadoFtp(Base):
    __tablename__ = "arquivo_baixado_ftp"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String(200))
    situacao = Column(String(50))
    baixado_em = Column(DateTime)


class PedidoHistorico(Base):
    __tablename__ = "pedido_historico"

    id = Column(Integer, primary_key=True, autoincrement=True)
    numero_pedido_ol = Column(String(50), ForeignKey("pedido.numero_pedido_ol", ondelete="CASCADE"), index=True)
    id_usuario = Column(Integer, ForeignKey("usuario.id"))
    acao = Column(String(80), index=True)
    detalhe = Column(Text)
    criado_em = Column(DateTime, server_default=_AGORA)

    pedido = relationship("Pedido", back_populates="historico")
    usuario = relationship("Usuario", back_populates="historico")


class ServicoMonitorado(Base):
    __tablename__ = "servico_monitorado"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String(100), unique=True)
    ultimo_heartbeat = Column(DateTime)
    status = Column(String(50))
    mensagem = Column(String(500))
    timeout_minutos = Column(Integer, default=10, server_default=text("10"))
    criado_em = Column(DateTime, server_default=_AGORA)
    atualizado_em = Column(DateTime, server_default=_AGORA_ATUALIZA, onupdate=func.now())


class Erros(Base):
    __tablename__ = "erros"

    id = Column(Integer, primary_key=True, autoincrement=True)
    descricao = Column(String(500))
    codigo_erp = Column(Integer)


class Parametro(Base):
    __tablename__ = "parametro"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chave = Column(String(80), unique=True)
    valor = Column(String(255))
    descricao = Column(String(255))
    id_usuario_atualizacao = Column(Integer, ForeignKey("usuario.id"))
    atualizado_em = Column(DateTime, server_default=_AGORA_ATUALIZA, onupdate=func.now())

    atualizado_por = relationship("Usuario")
