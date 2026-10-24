"""Muestra un código nuevo para el asistente web /install (docs/151).

- Sistema sin instalar: código de instalación (no vence).
- Sistema instalado: código de recuperación para crear o recuperar un
  administrador desde /install. Vence a los 30 minutos y sirve una vez.

Uso en producción (desde /opt/infomatt360):
    docker compose -f docker-compose.production.example.yml --env-file .env.production \\
        exec backend-1 python -m app.cli.install_code
"""

from __future__ import annotations

from app.core.config import settings
from app.db.session import SessionLocal
from app.services import install_code_service
from app.services.installation_service import installation_service


def main() -> None:
    try:
        with SessionLocal() as db:
            installed = installation_service.is_installed(db)
    except Exception:
        installed = False
    if installed:
        code = install_code_service.generate("recovery")
        print(f"Código de recuperación: {code}")
        print(f"Vence en {install_code_service.RECOVERY_MINUTES} minutos y sirve una sola vez.")
        print("Ábrelo en https://<tu dominio>/install y elige «Recuperar acceso de administrador».")
    elif not settings.installer_enforced:
        raise SystemExit("El asistente de instalación está desactivado (INSTALLER_ENFORCED=false).")
    else:
        code = install_code_service.generate("setup")
        print(f"Código de instalación: {code}")
        print("Ábrelo en https://<tu dominio>/install para empezar.")


if __name__ == "__main__":
    main()
