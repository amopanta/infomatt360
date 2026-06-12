"""Endpoints de salud del sistema.

Estos endpoints sirven para validar que el backend esta vivo y que la API
versionada responde correctamente.
"""

from fastapi import APIRouter

from app.core.config import settings

router = APIRouter()


@router.get("/", summary="Estado de salud de la API")
def health() -> dict[str, str]:
    """Retorna el estado basico de la API.

    En siguientes versiones este endpoint podra incluir estado de base de datos,
    Redis, MinIO, workers y almacenamiento externo.
    """
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
    }
