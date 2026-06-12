"""Configuracion central del backend.

Este modulo concentra variables de entorno y valores base. Mas adelante
se ampliara para manejar ambientes separados: desarrollo, pruebas, staging
y produccion.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuracion tipada de la aplicacion.

    Pydantic permite cargar variables desde .env y validar tipos, evitando
    errores silenciosos de configuracion en despliegues VPS o Docker.
    """

    app_name: str = "InfoMatt360 Core API"
    app_version: str = "0.1.0"
    environment: str = "development"
    debug: bool = True

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
