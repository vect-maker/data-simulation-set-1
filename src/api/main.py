"""Main FastAPI application entrypoint."""

from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.config import settings
from src.api.database import check_db_health, close_pool
from src.api.routers import antojitos, movigo, volcan

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("api.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle resources."""
    logger.info("Starting up FastAPI data exposure service...")
    yield
    logger.info("Shutting down FastAPI service...")
    close_pool()


app = FastAPI(
    title=settings.API_TITLE,
    description=settings.API_DESCRIPTION,
    version=settings.API_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Open CORS configuration for students (completely public, allow any origin)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Case Routers
app.include_router(antojitos.router)
app.include_router(volcan.router)
app.include_router(movigo.router)


@app.get("/", summary="Información y estado del servicio", tags=["Root"])
def root_info() -> dict:
    """Retorna información general de la API, enlaces a documentación y casos de estudio."""
    return {
        "name": settings.API_TITLE,
        "version": settings.API_VERSION,
        "description": settings.API_DESCRIPTION,
        "documentation": {
            "swagger_ui": "/docs",
            "redoc": "/redoc",
            "openapi_spec": "/openapi.json",
        },
        "cases": {
            "caso_1_antojitos": {
                "prefix": "/antojitos",
                "domain": "Cocina Fantasma / Delivery en Managua",
                "sample_endpoint": "/antojitos/ordenes?limit=10",
            },
            "caso_2_volcan": {
                "prefix": "/volcan",
                "domain": "Cooperativa El Volcán (Café de Exportación - Jinotega)",
                "sample_endpoint": "/volcan/lotes?limit=10",
            },
            "caso_3_movigo": {
                "prefix": "/movigo",
                "domain": "MoviGo (Transporte por Aplicación - Managua)",
                "sample_endpoint": "/movigo/viajes?limit=10",
            },
        },
    }


@app.get("/health", summary="Healthcheck de la API y PostgreSQL", tags=["Root"])
def health_check():
    """Verifica el estado operativo del servicio y la conectividad a la base de datos PostgreSQL."""
    db_ok, db_err = check_db_health()
    if not db_ok:
        return JSONResponse(
            status_code=503,
            content={
                "status": "degraded",
                "database": "disconnected",
                "error": db_err,
                "hint": "Verifique que el contenedor PostgreSQL esté arriba y las tablas cargadas con 'just load-all'.",
            },
        )
    return {"status": "ok", "database": "connected"}
