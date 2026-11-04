"""Cria o banco, as tabelas e os dados mínimos a partir dos modelos SQLAlchemy.

Equivalente ao "EnsureCreated + seed" do Entity Framework: os modelos em
app/models.py são a fonte da verdade do schema. Tudo é idempotente — pode rodar
a cada subida da API sem tocar no que já existe.

Escopo (não é um sistema de migrations):
  - banco ausente            -> CREATE DATABASE
  - tabela ausente           -> CREATE TABLE (com índices e FKs)
  - coluna nova no modelo    -> ALTER TABLE ADD COLUMN (somente colunas anuláveis ou com default)
  - alteração/remoção de coluna, tipo, índice ou FK em tabela existente -> NÃO é feita

Também pode ser executado direto:  python -m app.core.bootstrap_db
"""
import re

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateColumn

from ol_core.core.logger import logger

from app.core.config import settings
from app.core.database import Base, engine
from app.core.seed_data import ERROS, PARAMETROS

_CHARSET = "utf8mb4"
_COLLATION = "utf8mb4_unicode_ci"

_PERMISSOES_PERFIS = {
    "Administrador": {
        "pedidos": True, "arquivos": True, "usuarios": True, "dashboards": True,
        "ocorrencias": True, "reprocessar": True, "configuracoes": True, "monitoramento": True,
    },
    "Operador Logístico": {
        "pedidos": True, "arquivos": True, "dashboards": False,
        "ocorrencias": True, "reprocessar": True, "configuracoes": False,
    },
    "Gerente Comercial": {
        "pedidos": "somente_leitura", "arquivos": False, "dashboards": True,
        "ocorrencias": "somente_leitura", "reprocessar": False, "configuracoes": False,
    },
}

# (nome, timeout_minutos) — mesmos serviços do OL_Services
_SERVICOS = [
    ("importa_pedidos", 15),
    ("coleta_pedidos_ftp", 30),
    ("cancelados", 30),
    ("retornos", 15),
    ("espelhos", 15),
    ("envio_estoque", 30),
]

# Usuário técnico: o OL_CORE grava o histórico de ações automáticas em nome dele
# (contexto_historico._EMAIL_USUARIO_SISTEMA). Inativo e sem senha: não faz login.
EMAIL_USUARIO_SISTEMA = "sistema@painelol.local"


def garantir_banco() -> bool:
    """Cria o banco configurado em MYSQL_BANCO se ele não existir. Devolve True se criou."""
    nome = settings.mysql_banco
    if not re.fullmatch(r"[A-Za-z0-9_]+", nome):
        raise ValueError(f"MYSQL_BANCO inválido: {nome!r} (use apenas letras, números e _)")

    url_servidor = URL.create(
        "mysql+pymysql",
        username=settings.mysql_usuario,
        password=settings.mysql_senha,
        host=settings.mysql_host,
        port=settings.mysql_porta,
        query={"charset": _CHARSET},
    )
    engine_servidor = create_engine(url_servidor, isolation_level="AUTOCOMMIT")
    try:
        with engine_servidor.connect() as conn:
            existe = conn.execute(
                text("SELECT 1 FROM information_schema.schemata WHERE schema_name = :n"),
                {"n": nome},
            ).first()
            if existe:
                return False
            conn.execute(text(f"CREATE DATABASE `{nome}` CHARACTER SET {_CHARSET} COLLATE {_COLLATION}"))
            return True
    finally:
        engine_servidor.dispose()


def criar_tabelas() -> None:
    """Cria as tabelas ausentes e acrescenta colunas novas dos modelos às tabelas existentes."""
    import app.models  # noqa: F401  — registra os modelos no Base.metadata

    # Fotografia antes do create_all: só as tabelas que já existiam podem ganhar colunas.
    inspetor = inspect(engine)
    ja_existiam = set(inspetor.get_table_names())

    Base.metadata.create_all(engine)

    for tabela in Base.metadata.sorted_tables:
        if tabela.name not in ja_existiam:
            continue
        atuais = {c["name"] for c in inspect(engine).get_columns(tabela.name)}
        for coluna in tabela.columns:
            if coluna.name in atuais:
                continue
            if not coluna.nullable and coluna.server_default is None:
                logger.warning(
                    f"[bootstrap_db] Coluna `{tabela.name}`.`{coluna.name}` é obrigatória e sem default; "
                    "não adicionada automaticamente — criar por migration manual."
                )
                continue
            ddl = CreateColumn(coluna).compile(dialect=engine.dialect)
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE `{tabela.name}` ADD COLUMN {ddl}"))
            logger.info(f"[bootstrap_db] Coluna adicionada: `{tabela.name}`.`{coluna.name}`")


def popular_dados_iniciais() -> None:
    """Insere os registros que o sistema exige para operar, só quando ausentes."""
    from app.core.security import hash_password
    from app.models import Erros, Parametro, Perfil, ServicoMonitorado, Usuario

    with Session(engine) as db:
        existentes = {p.nome for p in db.query(Perfil.nome)}
        for nome, permissoes in _PERMISSOES_PERFIS.items():
            if nome not in existentes:
                db.add(Perfil(nome=nome, permissoes=permissoes))

        if not db.query(Usuario).filter(Usuario.email == EMAIL_USUARIO_SISTEMA).first():
            db.add(Usuario(nome="Sistema", email=EMAIL_USUARIO_SISTEMA, senha_hash=None, ativo=False))

        existentes = {s.nome for s in db.query(ServicoMonitorado.nome)}
        for nome, timeout in _SERVICOS:
            if nome not in existentes:
                db.add(ServicoMonitorado(
                    nome=nome, status="Aguardando", mensagem="Serviço não executou ainda",
                    timeout_minutos=timeout,
                ))

        # Só insere a chave que falta: valor/descrição já ajustados pelo usuário são preservados.
        existentes = {p.chave for p in db.query(Parametro.chave)}
        for chave, valor, descricao in PARAMETROS:
            if chave not in existentes:
                if chave == "cnpj_distribuidor" and not valor:
                    # Migração do .env para a tela: aproveita o CNPJ_DISTRIBUIDOR
                    # que o ambiente já tinha. Depois disso vale só o parâmetro.
                    valor = "".join(c for c in settings.cnpj_distribuidor if c.isdigit()) or None
                db.add(Parametro(chave=chave, valor=valor, descricao=descricao))

        # `erros` não tem chave única: só carrega o catálogo quando a tabela está vazia.
        if not db.query(Erros.id).first():
            db.add_all(Erros(descricao=d, codigo_erp=c) for d, c in ERROS)

        db.flush()
        _criar_admin_inicial(db, hash_password)
        db.commit()


def _criar_admin_inicial(db: Session, hash_password) -> None:
    """Cria o primeiro Administrador a partir de ADMIN_EMAIL/ADMIN_SENHA, se informados
    e se esse e-mail ainda não existir. Sem isso o banco novo não tem como logar."""
    from app.models import Perfil, Usuario

    if not (settings.admin_email and settings.admin_senha):
        return
    if db.query(Usuario).filter(Usuario.email == settings.admin_email).first():
        return
    perfil = db.query(Perfil).filter(Perfil.nome == "Administrador").first()
    db.add(Usuario(
        nome=settings.admin_nome, email=settings.admin_email,
        senha_hash=hash_password(settings.admin_senha),
        id_perfil=perfil.id if perfil else None, ativo=True,
    ))
    logger.info(f"[bootstrap_db] Administrador inicial criado: {settings.admin_email}")


def inicializar_banco() -> None:
    """Ponto de entrada: banco -> tabelas -> dados iniciais. Respeita DB_AUTO_CRIAR."""
    if not settings.db_auto_criar:
        logger.info("[bootstrap_db] DB_AUTO_CRIAR desligado — schema não será verificado.")
        return
    if garantir_banco():
        logger.info(f"[bootstrap_db] Banco '{settings.mysql_banco}' criado.")
    criar_tabelas()
    popular_dados_iniciais()
    logger.info(f"[bootstrap_db] Banco '{settings.mysql_banco}' pronto.")


if __name__ == "__main__":
    inicializar_banco()
