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
    auto_create_tables: bool = True

    # Cuando esta activo, el backend exige completar el instalador de primer
    # arranque (POST /api/v1/install/bootstrap) antes de servir el resto de
    # la API. Desactivado por defecto para no afectar despliegues e
    # instalaciones ya existentes (incluyendo la demo y las pruebas).
    installer_enforced: bool = False

    # En desarrollo se permite SQLite para pruebas rapidas. En produccion se
    # usara PostgreSQL y el valor vendra desde variables de entorno.
    database_url: str = "sqlite:///./infomatt360_dev.db"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout_seconds: int = 30
    db_pool_recycle_seconds: int = 1800

    # Clave de firma JWT. En produccion debe cambiarse por un secreto fuerte
    # entregado por variable de entorno o gestor de secretos.
    secret_key: str = "CHANGE_ME_IN_PRODUCTION"
    access_token_expire_minutes: int = 60
    # Sesion extendida para dispositivos de campo ya enrolados (ManagerQrToken),
    # que trabajan largas jornadas rurales sin conectividad para renovar el token.
    access_token_expire_minutes_field_device: int = 600
    refresh_token_expire_days: int = 7
    refresh_cookie_name: str = "infomatt360_refresh"
    refresh_cookie_secure: bool = False
    refresh_cookie_samesite: str = "strict"
    jwt_algorithm: str = "HS256"
    upload_directory: str = "./uploads"
    default_max_file_size_mb: int = 25
    frontend_url: str = "http://localhost:5173"
    cors_allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_use_tls: bool = True
    api_rate_limit_enabled: bool = True
    api_rate_limit_requests: int = 120
    api_rate_limit_window_seconds: int = 60
    api_rate_limit_api_key_requests: int = 10000
    api_rate_limit_high_volume_requests: int = 1000000
    api_rate_limit_trusted_proxy_ips: str = ""
    redis_url: str = ""
    api_rate_limit_backend: str = "memory"
    api_rate_limit_redis_prefix: str = "infomatt360:rate-limit"
    auth_throttle_backend: str = "db"
    auth_throttle_redis_prefix: str = "infomatt360:auth-throttle"
    api_key_profile_cache_ttl_seconds: int = 30
    permissions_cache_backend: str = "memory"
    permissions_cache_redis_prefix: str = "infomatt360:permissions"
    permissions_cache_ttl_seconds: int = 60
    request_logging_enabled: bool = True
    request_id_header: str = "X-Request-ID"
    metrics_enabled: bool = True
    bulk_worker_retry_backoff_seconds: int = 60
    bulk_worker_retry_max_backoff_seconds: int = 3600
    bulk_worker_stale_after_seconds: int = 1800
    bulk_worker_heartbeat_every_records: int = 100
    duplicate_check_window_days: int = 3
    backup_directory: str = "./backups"
    acta_batch_max_records: int = 200

    # Conector opcional de Google Drive para evidencias/backups. Vacio por
    # defecto: sin credenciales configuradas, el conector queda inactivo.
    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    google_oauth_redirect_uri: str = ""

    # Gateway opcional de WhatsApp via WAHA (https://waha.devlike.pro). Vacio
    # por defecto: sin URL configurada, el canal queda inactivo.
    waha_base_url: str = ""
    waha_api_key: str = ""
    waha_session: str = "default"

    # Auditoria semantica con IA/LLM. Vacio por defecto: sin proveedor
    # configurado, el analisis queda inactivo (se registra "skipped").
    # ai_audit_provider: "anthropic" | "openai_compatible" (cubre OpenAI,
    # DeepSeek, Zhipu/GLM y cualquier otro proveedor que implemente el
    # esquema de chat completions de OpenAI, cambiando solo la URL base) |
    # "gemini".
    ai_audit_provider: str = ""
    ai_audit_api_key: str = ""
    ai_audit_base_url: str = ""
    ai_audit_model: str = ""
    security_headers_enabled: bool = True
    content_security_policy: str = "default-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'self'"
    referrer_policy: str = "no-referrer"
    permissions_policy: str = "geolocation=(), microphone=(), camera=()"
    x_frame_options: str = "DENY"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8-sig", extra="ignore")


settings = Settings()
