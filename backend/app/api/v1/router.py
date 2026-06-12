"""Router principal de la version 1 de la API.

Cada modulo funcional tendra su propio router y se registrara aqui.
Esto permite mantener ordenado el backend a medida que crezcan los modulos.
"""

from fastapi import APIRouter

from app.api.v1.health import router as health_router

api_v1_router = APIRouter()

# Health versionado para monitoreo de API y pruebas de integracion.
api_v1_router.include_router(health_router, prefix="/health", tags=["health"])
