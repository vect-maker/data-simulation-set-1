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


TAGS_METADATA = [
    {
        "name": "Root",
        "description": (
            "Endpoints base de bienvenida, catálogo de casos de estudio y monitoreo del estado operativo "
            "del servicio y conectividad con la base de datos PostgreSQL."
        ),
    },
    {
        "name": "Caso 1: Antojitos Express",
        "description": (
            "### Cocina Fantasma (Dark Kitchen) y Delivery en Managua, Nicaragua\n\n"
            "Modela la operación de un restaurante digital con servicio a domicilio en el área urbana de Managua. "
            "Permite analizar la dinámica de pedidos, tiempos de entrega, canasta de platillos, rendimiento de repartidores, "
            "campañas promocionales y el impacto del clima diario sobre la demanda."
        ),
    },
    {
        "name": "Caso 2: Cooperativa El Volcán",
        "description": (
            "### Cooperativa Cafetalera y Exportación de Café de Altura (Jinotega / Matagalpa)\n\n"
            "Simulación de la cadena de valor completa del café especial en el norte montañoso de Nicaragua. "
            "Abarca desde las fincas productoras y sus variedades botánicas (Geisha, Bourbon, Pacamara, Caturra), "
            "cuadrillas de recolectores, recepción de lotes en cereza con catación SCAA, etapas agroindustriales en beneficios húmedos/secos "
            "(despulpado, fermentación, secado en patios), subastas de microlotes y embarques marítimos de exportación por Puerto Corinto."
        ),
    },
    {
        "name": "Caso 3: MoviGo",
        "description": (
            "### Plataforma Tecnológica de Movilidad Urbana y Transporte por App (Managua)\n\n"
            "Simulación de viajes urbanos bajo demanda en los cuadrantes de Managua. Incluye perfiles de usuarios y flota "
            "de socios conductores (`movigo_estandar`, `movigo_comfort`, `movigo_moto`), histórico de viajes con cálculo de tarifa dinámica "
            "(*surge pricing* 1.0x a 2.8x), eventos de lluvia e índice de congestión vial, telemetría GPS vehicular en tiempo real "
            "y programas de bonos e incentivos de horas de conexión."
        ),
    },
]

app = FastAPI(
    title=settings.API_TITLE,
    description=settings.API_DESCRIPTION,
    version=settings.API_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=TAGS_METADATA,
    contact={
        "name": "Cátedra del Proyecto Integrador",
        "url": "https://github.com/vect-maker/cs-datos-simulations",
    },
    license_info={
        "name": "MIT License",
        "identifier": "MIT",
    },
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


@app.get(
    "/",
    summary="Información y catálogo de casos de estudio",
    description=(
        "Punto de entrada principal de la API. Retorna metadatos del servicio, enlaces a las "
        "interfaces interactivas de Swagger UI y ReDoc, la especificación OpenAPI en JSON, "
        "y el directorio de los tres casos de estudio de Nicaragua con sus prefijos y rutas de ejemplo."
    ),
    response_description="Metadatos globales del servicio y directorio de casos de estudio",
    tags=["Root"],
)
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


@app.get(
    "/health",
    summary="Healthcheck de la API y PostgreSQL",
    description=(
        "Verifica el estado operativo del servicio web FastAPI y la conectividad activa con el "
        "servidor de base de datos PostgreSQL (`integrador_db`). Retorna HTTP 200 si todo opera con normalidad, "
        "o HTTP 503 con diagnóstico de error si la base de datos no está disponible."
    ),
    response_description="Diagnóstico operativo del servicio y conectividad con PostgreSQL",
    responses={
        200: {
            "description": "Servicio FastAPI en ejecución y base de datos PostgreSQL conectada exitosamente.",
            "content": {"application/json": {"example": {"status": "ok", "database": "connected"}}},
        },
        503: {
            "description": "Base de datos PostgreSQL no accesible o error de conexión.",
            "content": {
                "application/json": {
                    "example": {
                        "status": "degraded",
                        "database": "disconnected",
                        "error": "connection to server at 'localhost' failed",
                        "hint": "Verifique que el contenedor PostgreSQL esté arriba y las tablas cargadas con 'just load-all'.",
                    }
                }
            },
        },
    },
    tags=["Root"],
)
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
