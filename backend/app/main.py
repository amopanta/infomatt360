"""Entrada principal del backend de InfoMatt360.

Este archivo crea la instancia FastAPI y registra las rutas base.
La logica de negocio no debe concentrarse aqui; cada modulo debe vivir en
su paquete correspondiente para mantener el sistema mantenible.
"""

from fastapi import FastAPI

from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.db.init_db import init_db


def create_app() -> FastAPI:
    """Construye y configura la aplicacion FastAPI.

    Se usa una funcion fabrica para facilitar pruebas, configuracion por
    ambiente y futuros despliegues multiworker.
    """
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Core API para InfoMatt360",
    )

    @app.on_event("startup")
    def on_startup() -> None:
        """Inicializa tablas en desarrollo.

        En produccion esta responsabilidad sera de Alembic para controlar
        versiones de esquema y migraciones.
        """
        init_db()

    # Ruta simple para balanceadores, monitoreo y pruebas iniciales.
    @app.get("/health", tags=["system"])
    def health_check() -> dict[str, str]:
        return {"status": "ok", "service": settings.app_name}

    # Todas las rutas versionadas viven bajo /api/v1.
    app.include_router(api_v1_router, prefix="/api/v1")
    return app


app = create_app()
