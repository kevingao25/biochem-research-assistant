import logging

from fastapi import APIRouter
from sqlalchemy import text

from src.dependencies import DatabaseDep, OllamaDep, QdrantDep, SettingsDep
from src.exceptions import OllamaConnectionError, OllamaException
from src.schemas.api.health import HealthResponse, ServiceStatus

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check(
    settings: SettingsDep,
    database: DatabaseDep,
    qdrant: QdrantDep,
    ollama: OllamaDep,
) -> HealthResponse:
    """Comprehensive health check with per-service status."""
    services: dict = {}
    overall = "ok"

    # PostgreSQL
    try:
        with database.get_session() as session:
            session.execute(text("SELECT 1"))
        services["postgres"] = ServiceStatus(status="healthy", message="Connected")
    except Exception as e:
        services["postgres"] = ServiceStatus(status="unhealthy", message=str(e))
        overall = "degraded"

    # Qdrant
    try:
        ok = qdrant.health_check()
        services["qdrant"] = ServiceStatus(
            status="healthy" if ok else "unhealthy",
            message="Connected" if ok else "Not responding",
        )
        if not ok:
            logger.warning("Qdrant health_check returned unhealthy")
            overall = "degraded"
    except Exception as e:
        services["qdrant"] = ServiceStatus(status="unhealthy", message=str(e))
        overall = "degraded"

    # Ollama
    try:
        result = await ollama.health_check()
        services["ollama"] = ServiceStatus(status=result["status"], message=result["message"])
        if result["status"] != "healthy":
            overall = "degraded"
    except (OllamaConnectionError, OllamaException) as e:
        services["ollama"] = ServiceStatus(status="unhealthy", message=str(e))
        overall = "degraded"

    return HealthResponse(
        status=overall,
        version=settings.app_version,
        environment=settings.environment,
        service_name=settings.service_name,
        services=services,
    )
