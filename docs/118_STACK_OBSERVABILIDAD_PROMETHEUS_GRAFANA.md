# 118. Stack de observabilidad: Prometheus + Grafana

## Qué cierra esto

El resto de la categoría C de la auditoría técnica externa de julio 2026 relacionado con observabilidad: el endpoint `/api/v1/health/metrics/prometheus` ya existía y era *compatible* con scraping Prometheus, pero no había ningún `prometheus.yml` ni stack de observabilidad desplegado — `README.md` lo listaba como acción pendiente. Con la decisión de hosting ya tomada (VPS/Docker Compose, docs/117), este ítem construye el stack real sobre la misma receta de referencia.

## Decisiones de diseño

**Autenticación de scraping: token JWT de larga duración, no un endpoint sin auth nuevo.** `require_metrics_viewer` (el mismo endpoint que ya usa cualquier usuario humano) exige un JWT válido — Prometheus no puede iniciar sesión interactivamente. En vez de debilitar el endpoint existente agregando un modo sin autenticación, `backend/app/cli/generate_metrics_token.py` crea (de forma idempotente) un usuario de servicio no interactivo, con un rol asignado a nivel de Organización (mismo patrón "Administrador nacional" de docs/101 — las métricas son globales al proceso, no de un proyecto específico) y emite un JWT válido por 10 años. No existe un permiso dedicado de "solo ver métricas" en el catálogo (`app/core/permissions.py::METRICS_VIEW_PERMISSIONS`); se reutiliza `integrations.api_keys.manage` por ser el más cercano a "cuenta técnica/de integración" entre las 4 opciones disponibles — decisión documentada explícitamente, no silenciosa. El token vive en `secrets/metrics_token` (nunca en git, nunca en el compose ni en variables de entorno) montado como `bearer_token_file` en `deploy/prometheus.yml`.

**Prometheus scrapea `backend-1`/`backend-2` directo, nunca a través de `backend-lb`.** `metrics_service.py` guarda sus contadores en memoria por proceso (no en Redis ni Postgres) — si se scrapeara a través del balanceador de E-001, cada scrape caería en una réplica distinta al azar y Prometheus vería una serie completamente inconsistente (contadores que suben y bajan sin sentido). Apuntar a cada réplica como target independiente (con label `instance`) es el patrón correcto y estándar de Prometheus para servicios con múltiples réplicas — la agregación entre réplicas se hace en tiempo de consulta con PromQL (`sum by (...)`), no en el scraping.

**Prometheus no publica puerto al host; Grafana sí.** La UI de Prometheus no tiene autenticación propia — exponerla directo a internet sería un hueco de seguridad real. Se consulta a través de Grafana (que sí tiene login, contraseña en `GF_SECURITY_ADMIN_PASSWORD`) o vía túnel SSH para debug directo.

**Dashboard inicial provisionado automáticamente, no configurado a mano.** `deploy/grafana/provisioning/` (datasource + dashboard JSON) se monta como volumen de solo lectura — al primer arranque, Grafana ya tiene el datasource de Prometheus y el dashboard "InfoMatt360 - Visión general" listos, sin que el operador tenga que hacer clic en nada. El dashboard cubre: réplicas activas (`up{job="infomatt360-backend"}`), tasa de errores 5xx, requests/seg por réplica, latencia p50/p95/p99, requests por familia de status, y throughput del worker bulk — construido directamente sobre los nombres de métrica reales que ya expone `metrics_service.py::prometheus_text()`.

## Archivos nuevos/modificados

- `backend/app/cli/generate_metrics_token.py` (nuevo): usuario de servicio + rol + asignación de organización + emisión de JWT, idempotente.
- `backend/tests/test_generate_metrics_token.py` (nuevo, 3 casos): sin organización activa, idempotencia + permiso realmente otorgable, el token decodifica al usuario correcto.
- `deploy/prometheus.yml` (nuevo): scrape config con los 2 targets directos y `bearer_token_file`.
- `deploy/grafana/provisioning/datasources/prometheus.yml` (nuevo): datasource con UID fijo `prometheus`.
- `deploy/grafana/provisioning/dashboards/dashboards.yml` + `infomatt360-overview.json` (nuevos): provider + dashboard de 6 paneles.
- `docker-compose.production.example.yml`: servicios `prometheus` (sin puerto al host) y `grafana` (puerto `3000`), volúmenes `prometheus_data`/`grafana_data`.
- `.env.production.example`: `GF_SECURITY_ADMIN_PASSWORD` nuevo.
- `.gitignore`/`.dockerignore`: `secrets/` excluido — ahí vive `metrics_token`, nunca debe llegar a git ni a una imagen.
- `docs/61_DESPLIEGUE_PRODUCCION_REFERENCIA.md`: pasos 7-8 nuevos (generar token, levantar observabilidad) + secciones de componentes.
- `docs/62_CHECKLIST_GO_LIVE.md` / `docs/64_ROLLBACK_OPERATIVO.md` / `docs/ARQUITECTURA_TECNICA_INFOMATT360.md`: topología, tablas de servicios/puertos/imágenes, diagrama Mermaid, y el párrafo de la sección de integraciones que antes marcaba esto como "Pendiente de confirmar por infraestructura".
- `scripts/check-production-package.ps1`: checks nuevos para los 4 archivos de observabilidad y su contenido.

## Pruebas

`backend/tests/test_generate_metrics_token.py` (3 casos, patrón SQLite en memoria ya usado en todo el repo): sin organización activa devuelve `None`; correr `ensure_metrics_service_user` dos veces es idempotente (mismo usuario, mismo rol, una sola asignación) y el rol otorga un permiso real de `METRICS_VIEW_PERMISSIONS` verificado contra `require_any_permission`; el JWT emitido decodifica al `user_id`/`auth_version` correctos. `pytest -q` completo del backend después del cambio: **423 passed** (420 + 3 nuevos), mismos 5 errores preexistentes no relacionados.

`python -c "import yaml; ..."` sobre los 4 archivos YAML nuevos/modificados: válidos. `.\scripts\check-production-package.ps1`: **Paquete productivo de referencia OK**.

## Verificación real con Podman (2026-07-23)

Mismo criterio que docs/117 — no solo validación estática, sino el stack completo levantado de verdad contra Postgres real:

- **Prometheus scrapeando de verdad:** `GET /api/v1/targets` mostró ambos targets (`backend-1:8000`, `backend-2:8000`) en `health: "up"`, `lastError: ""`.
- **Bug real encontrado y corregido durante esta prueba:** el primer intento falló con `404 Not Found` en ambos targets — `deploy/prometheus.yml` apuntaba a `/api/v1/metrics/prometheus`, pero el router de salud está montado con prefijo `/health` (`api_v1_router.include_router(health_router, prefix="/health", ...)`), así que la ruta real es `/api/v1/health/metrics/prometheus`. Corregido en `deploy/prometheus.yml`, `backend/app/cli/generate_metrics_token.py` (docstring/mensaje) y `docs/ARQUITECTURA_TECNICA_INFOMATT360.md`; re-verificado con el mismo stack y confirmado `up` en ambos targets.
- **Métricas reales confirmadas por instancia:** `infomatt360_http_requests_total` devolvió valores distintos para `backend-1` (32) y `backend-2` (18) — prueba directa de que el scraping por-réplica funciona como se diseñó (no una serie mezclada vía el balanceador).
- **Grafana confirmado end-to-end, no solo "arriba":** `GET /api/health` respondió `database: ok`; `GET /api/datasources` mostró el datasource Prometheus provisionado automáticamente con la URL correcta; `GET /api/search` mostró el dashboard "InfoMatt360 - Visión general" provisionado con el UID esperado. Se consultaron 3 de los 6 paneles reales a través del proxy de datasource de Grafana (no directo a Prometheus) y devolvieron datos correctos: réplicas activas = `2`, latencia p50/p95/p99 = `4.63ms`/`72.49ms`/`228.5ms`, requests/seg por réplica con valores distintos por `instance`.
- Token generado con el comando real documentado (`podman exec ... python -m app.cli.generate_metrics_token`) contra una base recién migrada — confirmó además que toda instalación real de este proyecto ya tiene una organización por defecto (`Organizacion por defecto`, `slug=default`) creada por una migración anterior, así que la ruta "sin organización activa" del CLI es una guarda defensiva que en la práctica nunca se dispara.
- Stack completo desmontado al final (`podman compose down -v`, imágenes de prueba y archivos `.env`/`.env.production`/`secrets/` temporales eliminados) — nada residual.

**Límite que sigue siendo real:** esto prueba que el pipeline de scraping/visualización funciona correctamente, no el comportamiento bajo carga real ni en un despliegue multi-host real — eso sigue pendiente del script k6/locust (aún no construido) y de un despliegue real en el VPS del usuario.

## Lo que queda fuera de esta sesión

De la categoría C de la auditoría técnica externa: solo queda **E-003 (PgBouncer)** y el **script de prueba de carga (k6/locust)**. La categoría D (descomposición de `User`, migración a SQLAlchemy async) sigue explícitamente diferida hasta tener evidencia real de carga.
