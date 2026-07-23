# 119. Script de prueba de carga (k6)

## Qué cierra esto

El último punto abierto de la categoría C de la auditoría técnica externa de julio 2026: el veredicto "madurez técnica 72/100, no certificada para 3.000 usuarios concurrentes / 300.000 requests simultáneos" (docs/108) nunca tuvo, hasta ahora, ninguna herramienta en el repositorio para generar esa evidencia. `loadtest/k6-infomatt360.js` es esa herramienta.

## Diseño

**Login una sola vez en `setup()`, no en cada iteración.** El endpoint de login tiene throttling real (`app/api/v1/auth.py`: 5 intentos por email+IP y 25 por IP cada 15 minutos). Simular miles de logins/segundo no reflejaría un uso real (los usuarios inician sesión una vez y trabajan horas con el mismo token) y dispararía ese throttle de inmediato, invalidando la prueba. El token se obtiene una vez y se reparte entre todos los VUs.

**Dos escenarios, el de escritura opt-in.** El escenario de lectura (`GET /api/v1/health/ready` + `GET /api/v1/runtime/template/{id}/records/search` paginado) es seguro de correr contra cualquier entorno. El escenario de escritura (`POST /api/v1/runtime/save`) crea registros Runtime reales — solo se activa con `ENABLE_WRITES=true`, y cada registro queda marcado de forma identificable (`nombre`/`observaciones` contienen `k6-load-test`) para poder ubicarlos y borrarlos después. Documentado explícitamente: no correr contra un proyecto de producción real sin avisar al responsable.

**Escala configurable vía variables de entorno, default mínimo y seguro.** `TARGET_VUS`, `RAMP_DURATION`, `SUSTAIN_DURATION` controlan la escala real de la prueba — por defecto (5 VUs, ~90s) es seguro correrlo siempre; llegar a los 3.000 usuarios de la auditoría es una elección explícita del operador (`-e TARGET_VUS=3000`), no el comportamiento por defecto.

**Thresholds con tags por endpoint.** `http_req_duration{endpoint:search}` con `p(95)<500ms`/`p(99)<1500ms`, `http_req_failed<1%` global — k6 termina con código de salida distinto de cero si no se cumplen, utilizable en un pipeline.

## Hallazgo real de la verificación: el rate limiting por IP corta la prueba antes de acercarse a 3.000 usuarios

Al correr el script por primera vez contra el stack levantado con Podman, el escenario de lectura mostró **20% de fallos** (`http_req_failed` cruzó el threshold). Investigado: no era un bug del script ni del backend — `API_RATE_LIMIT_REQUESTS`/`API_RATE_LIMIT_WINDOW_SECONDS` (default `120`/`60s`) se aplican por IP de origen, y **todos los VUs de k6 corriendo desde una sola máquina comparten esa misma IP** tal como la ve `backend-lb` (confirmado contando `429` en los logs de `backend-1`/`backend-2`: 122 respuestas `429`, casi exactamente el número de checks fallidos). Esto es el límite antiabuso funcionando exactamente como está diseñado, no un defecto — pero significa que **una prueba de carga real de 3.000 usuarios corrida desde una sola máquina se autolimitaría mucho antes de llegar a esa escala**, sin que eso diga nada sobre la capacidad real de la aplicación.

Documentado en `loadtest/README.md`: subir `API_RATE_LIMIT_REQUESTS` temporalmente antes de correr la prueba grande, y revertirlo después — mismo patrón de "config temporal para verificación, revertida al terminar" ya usado en todo este proyecto para archivos `.env`/`.env.local`.

## Archivos nuevos

- `loadtest/k6-infomatt360.js`: script principal.
- `loadtest/README.md`: uso básico, cómo generar la evidencia de 3.000 usuarios, advertencia sobre el escenario de escritura, explicación del rate limiting por IP, límite honesto sobre qué puede y no puede probarse desde esta máquina.
- `docs/61_DESPLIEGUE_PRODUCCION_REFERENCIA.md`: sección "Prueba de carga (loadtest/)".
- `docs/62_CHECKLIST_GO_LIVE.md`: sección "6b. Prueba de carga" nueva.
- `docs/ARQUITECTURA_TECNICA_INFOMATT360.md`: la sección 8 ya no dice "script aún no construido" — documenta el hallazgo del rate limiting.

## Verificación real con Podman (2026-07-23)

Mismo criterio que docs/117/docs/118 — no solo escrito, sino corrido de verdad:

- **Primer intento (5 VUs, rate limit por defecto):** `http_req_failed=20.06%`, threshold `rate<0.01` cruzado — investigado y explicado arriba, no un bug.
- **Con `API_RATE_LIMIT_REQUESTS` subido temporalmente, 20 VUs, 40s:** **100% de checks exitosos** (1155/1155), `http_req_failed=0.00%`, todos los thresholds cumplidos (`search` p95=66.87ms, p99=281.22ms; `health` p95=51.48ms).
- **Escenario de escritura (`ENABLE_WRITES=true`, 5 VUs lectura + 3 VUs escritura, 25s):** también **100% exitoso** (257/257 checks), incluyendo `save devolvio 200`; confirmado por consulta directa a Postgres que se crearon 60 registros marcados con `k6-load-test`, correctamente identificables.
- Base de datos de prueba sembrada con `python -m app.cli.seed_demo` antes de la corrida (una base recién migrada no tiene usuario/proyecto/plantilla demo).
- Stack desmontado al final (`podman compose down -v`), imagen de prueba y archivos `.env`/`.env.production` temporales eliminados.

**Límite explícito, no fingido:** esto prueba que el script funciona correctamente de punta a punta (autenticación, lectura paginada, escritura marcada, thresholds), no que la aplicación soporta 3.000 usuarios reales. Generar esa evidencia real requiere correr el script contra un despliegue real en el VPS que decida el usuario, con `TARGET_VUS=3000` y el rate limiting ajustado a propósito — una VM de desarrollo con un solo host Podman no puede producir un número creíble a esa escala.

## Lo que queda fuera de esta sesión

De la categoría C de la auditoría técnica externa: solo queda **E-003 (PgBouncer)**. La categoría D (descomposición de `User`, migración a SQLAlchemy async) sigue explícitamente diferida hasta que el usuario corra la prueba de carga real de 3.000 usuarios con esta herramienta y esa evidencia muestre que hace falta.
