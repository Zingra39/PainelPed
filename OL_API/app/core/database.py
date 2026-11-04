from urllib.parse import quote_plus

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from ol_core.core.conexao import eh_erro_conexao_mysql, traduzir_erros_de_conexao

from app.core.config import settings

_senha = quote_plus(settings.mysql_senha)
DATABASE_URL = (
    f"mysql+pymysql://{settings.mysql_usuario}:{_senha}"
    f"@{settings.mysql_host}:{settings.mysql_porta}/{settings.mysql_banco}"
    f"?charset=utf8mb4"
)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_timeout=settings.mysql_pool_timeout,
    connect_args={
        "connect_timeout": settings.mysql_connect_timeout,
        "read_timeout": settings.mysql_read_timeout,
        "write_timeout": settings.mysql_write_timeout,
    },
    echo=False,
)

# Banco fora do ar / conexão perdida vira ErroConexaoBanco (503 no handler do
# main.py) em vez de OperationalError cru (500 genérico).
traduzir_erros_de_conexao(engine, "MySQL", eh_erro_conexao_mysql)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    # Mesmo charset/collation do banco original; sem isso o FK por varchar
    # (numero_pedido_ol) falha com "incompatible" entre tabelas de collations distintas.
    __table_args__ = {
        "mysql_engine": "InnoDB",
        "mysql_charset": "utf8mb4",
        "mysql_collate": "utf8mb4_unicode_ci",
    }


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
