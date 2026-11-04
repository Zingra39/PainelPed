from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from ol_core.core.config import carregar_ambiente

# Pasta da API (OL_API/), independente do diretório de onde ela é iniciada.
PASTA_API = Path(__file__).resolve().parents[2]

# Uma única carga para o processo inteiro: variáveis já definidas (NSSM) >
# PAINEL_ENV_FILE > OL_API/.env. Vai para os.environ, então o ol_core usado
# pela API enxerga a MESMA configuração que o Settings abaixo — antes o
# Settings lia OL_API/.env e o ol_core lia o próprio .env, separado.
ENV_FILE = carregar_ambiente(PASTA_API / ".env")


class Settings(BaseSettings):
    # Sem env_file: lê só os.environ, já preenchido por carregar_ambiente.
    model_config = SettingsConfigDict(case_sensitive=False, extra="ignore")

    mysql_host: str
    mysql_porta: int = 3306
    mysql_banco: str
    mysql_usuario: str
    mysql_senha: str

    # Timeouts (segundos) da conexão com o MySQL — mesmas variáveis lidas
    # pelo ol_core (OL_CORE/ol_core/core/conexao.py). Estourou = 503 com a
    # mensagem de problema de conexão, em vez de a requisição ficar pendurada.
    mysql_connect_timeout: int = 5
    mysql_read_timeout: int = 30
    mysql_write_timeout: int = 30
    # Espera máxima por uma conexão livre no pool da API.
    mysql_pool_timeout: int = 10

    # Cria banco/tabelas/dados iniciais na subida (app/core/bootstrap_db.py).
    # Desligar em produção se o schema for gerenciado por fora.
    db_auto_criar: bool = True
    # Opcionais: se informados, a subida cria este Administrador num banco novo.
    admin_nome: str = "Administrador"
    admin_email: str = ""
    admin_senha: str = ""

    erp_servidor: str
    erp_banco: str
    erp_usuario: str
    erp_senha: str

    cnpj_distribuidor: str = ""

    cors_origins: str = ""

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    # Chave usada por chamadas serviço-a-serviço (ex.: heartbeat do OL_Services).
    # Sem valor configurado, esses endpoints ficam bloqueados por padrão (fail-closed).
    servicos_api_key: str = ""


settings = Settings()
