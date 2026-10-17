### [BITACORA DE ESTADO - FECHA: 2026-10-17]

- **Objetivo activo:** InfoMatt360 — Plataforma operativa unificada para gestión de proyectos: formularios dinámicos, captura en campo, registros, evidencias, reportes, mapas, flujos de aprobación, mensajería, API keys, sincronización masiva y seguridad de usuarios.

- **Avances consolidados:**
  - MVP funcional reforzado con 138 documentos técnicos publicados.
  - **Backend** (FastAPI/Python): autenticación con refresh token + MFA TOTP, constructor de formularios + runtime de captura (55 tipos de campo), registros/evidencias/reportes XLSX, flujos de aprobación configurables, API keys con rate limit, sync bulk con worker separado, métricas operativas Prometheus, GIS real PostGIS, auditoría semántica con IA multi-proveedor, ERP headless, WhatsApp/WAHA, base espejo real (Postgres/SQLite), carga masiva Excel, conectores BI (Power BI/Tableau), bandeja IMAP, importador multiformato.
  - **Frontend** (React/TypeScript/Vite): panel admin completo con módulos de storage, flujos de aprobación, API keys, ERP, XLSForm, gobernanza, WhatsApp, mirror, backups, branding, auditoría IA, proveedores IA por API.
  - **Mobile** (React Native / Expo, repo `amopanta/infomatt360-mobile`): app móvil oficial con sincronización offline, captura de huella y verificación en dispositivo. El módulo `mobile/` (Express + Capacitor) se retiró: no estaba conectado al backend principal (ver `docs/140`).
  - **Desktop** (Electron): impresión nativa de actas, bridge con el backend.
  - **Infraestructura:** Docker Compose productivo, PgBouncer, balanceo de carga, Prometheus/Grafana, scripts k6, deploy en VPS con DNS/SSL.
  - **14 hallazgos de auditoría contra documento maestro:** todos cerrados (con recortes de alcance acordados).
  - **Auditoría técnica externa (julio 2026):** categorías A, B, C cerradas. Solo categoría D diferida (refactors grandes).
  - **Último commit (hoy 2026-10-17):** "Add project AI API provider connections for form builder" — proveedores de IA configurables por proyecto para el constructor de formularios.

- **Decisiones arquitectónicas tomadas:**
  - Tenant lógico (`Organization` sobre `Project`) en vez de aislamiento físico por base de datos.
  - SQLAlchemy síncrono (migración a async diferida hasta evidencia de carga real).
  - GIS: Leaflet + API GeoJSON con radio en vez de WMS/WFS literal.
  - Conectores BI: solo Power BI y Tableau con conector propio; Looker/Metabase via base espejo.
  - Proveedores IA: adaptadores para Gemini, Anthropic, OpenAI-compatible (OpenRouter, DeepSeek, Groq) + URL personalizada.

- **Archivos y estructuras clave:**
  - Repositorio: `amopanta/infomatt360` (GitHub, público)
  - Repositorio móvil: `amopanta/infomatt360-mobile`
  - Backend: `backend/app/` (FastAPI, Alembic migrations)
  - Frontend: `frontend/src/` (React + TypeScript + Vite)
  - Mobile: repositorio aparte `amopanta/infomatt360-mobile` (`src/`)
  - Desktop: `desktop/src/` (Electron)
  - Documentación: `docs/` (140 archivos, del 00 al 138 + arquitectura técnica)
  - Deploy: `deploy/`, `docker-compose.production.example.yml`
  - Scripts: `scripts/` (init, demo, tests, doctor, release, UAT)

- **Pendientes críticos (Next Steps):**
  1. Configurar `AI_AUDIT_PROVIDER` y `AI_AUDIT_API_KEY` en VPS para activar sugerencias IA.
  2. Pruebas de captura con usuarios reales y respuesta del proveedor de IA.
  3. Base Espejo: UI de frontend, integración con ScheduledTask, soporte MySQL/SQL Server, modo incremental.
  4. Carga masiva de asignaciones: ampliar a formulario/territorio/dispositivo (requiere crear modelos de datos).
  5. Registros históricos: soporte de archivos/GPS/subformularios/multiselect/calculados.
  6. Conectores BI: Looker/Metabase/Superset via conexión SQL directa a base espejo.
  7. Categoría D auditoría técnica: descomponer entidad `User`, migrar a SQLAlchemy async.
  8. Pruebas UAT con usuarios finales (plan piloto documentado en docs/68-70).
  9. Reserva concurrente de turnos en la agenda de seguimientos.

- **Bloqueos o advertencias:**
  - VPS no tiene clave IA configurada; la opción de IA devuelve mensaje de configuración pendiente.
  - La impresión nativa en Electron no se ha probado con impresora física real.
  - Borradores locales del móvil permanecen en el dispositivo; no sustituyen sync del backend.
  - Migración async (categoría D) diferida: riesgo bajo a escala actual, alto si se escala a producción industrial.
