"""Router principal de la version 1 de la API.

Cada modulo funcional tendra su propio router y se registrara aqui.
Esto permite mantener ordenado el backend a medida que crezcan los modulos.
"""

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.health import router as health_router
from app.api.v1.identity import router as identity_router
from app.api.v1.security import router as security_router

api_v1_router = APIRouter()

# Health versionado para monitoreo de API y pruebas de integracion.
api_v1_router.include_router(health_router, prefix="/health", tags=["health"])

# Autenticacion central para web, Android y escritorio.
api_v1_router.include_router(auth_router, prefix="/auth", tags=["auth"])

# Seguridad de sesion actual y endpoints protegidos base.
api_v1_router.include_router(security_router, prefix="/security", tags=["security"])

# Identidad, proyectos y roles base.
api_v1_router.include_router(identity_router, prefix="/identity", tags=["identity"])
