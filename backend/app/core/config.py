"""Configuracion central del backend.

Este modulo concentra variables de entorno y valores base para que el sistema
pueda ejecutarse en desarrollo, pruebas, staging o produccion sin cambiar codigo.
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

    # En desarrollo se permite SQLite para pruebas rapidas. En produccion se
    # usara PostgreSQL y el valor vendra desde variables de entorno.
    database_url: str = "sqlite:///./infomatt360_dev.db"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
