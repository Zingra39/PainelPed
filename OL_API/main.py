from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ol_core.core.exceptions import ErroConexaoBanco
from ol_core.core.logger import logger
from ol_core.core.config import inicializar_processo

from app.core.config import PASTA_API, settings
from app.core.bootstrap_db import inicializar_banco
from app.core.database import SessionLocal
from app.core.deps import PERFIS_CONHECIDOS, perfis_ausentes_no_banco
from app.routers import auth, pedidos, ocorrencias, arquivos, dashboard, usuarios, servicos, industrias, erros, parametros


# .env já carregado por app.core.config; aqui liga os logs (LOG_DIR ou
# OL_API/logs/api.log) e registra de onde veio a configuração.
inicializar_processo("api", PASTA_API)

def _conferir_perfis():
    """Confere, no boot, se os perfis que o código exige existem no banco.

    A autorização de todo endpoint compara `perfil.nome` com os literais de
    require_perfis(...). Quando esse nome não confere — nome gravado com dano
    de charset ("Operador Log?stico"), perfil renomeado à mão, banco errado no
    .env —, todos os usuários daquele perfil recebem 403 em todas as telas,
    sem nenhuma pista. Já aconteceu em produção; a partir de agora o problema
    aparece no log da subida, e não numa investigação de horas.

    Nunca impede a API de subir: falha de checagem só gera log.
    """
    try:
        with SessionLocal() as db:
            from app.models import Perfil

            perfis = db.query(Perfil).order_by(Perfil.id).all()
            logger.info(
                f"Perfis cadastrados em '{settings.mysql_banco}': "
                + ", ".join(f"id={p.id} {ascii(p.nome)}" for p in perfis)
            )

            ausentes = perfis_ausentes_no_banco(db)
            if ausentes:
                logger.error(
                    "ATENCAO: os perfis a seguir sao exigidos pelo codigo mas nao "
                    f"foram encontrados na tabela `perfil` do banco '{settings.mysql_banco}': "
                    f"{ascii(ausentes)}. Todo usuario com esse perfil vai receber 403 em "
                    "todas as telas. Conferir grafia/acentuacao da coluna `perfil.nome` "
                    "(usar um cliente em utf8mb4) e se o .env aponta para o banco certo."
                )
            else:
                logger.info(
                    f"Checagem de perfis OK — os {len(PERFIS_CONHECIDOS)} perfis "
                    "esperados pelo codigo existem no banco."
                )
    except Exception as err:
        logger.warning(f"Nao foi possivel conferir os perfis na subida da API: {err}")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        inicializar_banco()
    except Exception as err:
        logger.exception(f"Falha ao criar/atualizar o banco '{settings.mysql_banco}': {err}")
    _conferir_perfis()
    yield


app = FastAPI(
    title="PainelPed API",
    description="API de gerenciamento de pedidos OL — DispFarm.",
    version="1.0.0",
    lifespan=lifespan,
)

_DEFAULT_CORS = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://localhost:8080"
]
_CORS_ORIGINS = (
    [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    if settings.cors_origins
    else _DEFAULT_CORS
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # Card #42 — sem isso o navegador bloqueia a leitura de headers
    # customizados via JS (não fazem parte da lista safelisted padrão do
    # CORS), então o frontend não conseguiria ler X-Arquivo-Origem.
    expose_headers=["X-Arquivo-Origem"],
)

@app.exception_handler(ErroConexaoBanco)
async def _erro_conexao_banco(_request: Request, erro: ErroConexaoBanco):
    """Banco (MySQL ou ERP) fora do ar / timeout: 503 com mensagem clara para
    a tela, em vez de 500 genérico. A causa técnica fica só no log."""
    logger.error(f"{erro.detail} Causa: {erro.causa}")
    return JSONResponse(status_code=503, content={"detail": erro.detail})


app.include_router(auth.router)
app.include_router(pedidos.router)
app.include_router(ocorrencias.router)
app.include_router(arquivos.router)
app.include_router(dashboard.router)
app.include_router(usuarios.router)
app.include_router(servicos.router)
app.include_router(industrias.router)
app.include_router(erros.router)
app.include_router(parametros.router)


@app.get("/", tags=["Health"])
def health():
    return {"status": "ok", "app": "PainelOL API"}
