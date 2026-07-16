# 108. Cache de permisos efectivos

## Qué cierra esto

El hallazgo **E-004** de la categoría C de la auditoría técnica externa de julio 2026 (escalabilidad). De los 4 hallazgos de esa categoría, es el único que era código puro y no dependía de una decisión de infraestructura/hosting pendiente (réplicas, PgBouncer, pruebas de carga de 3.000 usuarios): el resto sigue bloqueado por falta de un entorno de staging real, sin cambios en esta sesión.

`get_project_permissions` (`backend/app/api/permissions.py`) se llama en prácticamente cada endpoint de escritura (~60 puntos de llamada en todo el backend, vía `require_project_permission`/`require_any_project_permission`), y hacía **hasta 3 queries por chequeo** sin ningún cache: la asignación de proyecto del usuario, el proyecto (para saber si pertenece a una organización), y la asignación a nivel de organización si aplica ("Administrador nacional", ver docs/101). Medido directamente contra una BD real: 3 queries en la primera llamada, 0 en la segunda con el cache activo.

## Diseño

Nuevo `backend/app/services/permission_cache_service.py`, siguiendo el mismo patrón memoria/Redis-opcional que ya usan `ApiKeyProfileCache` (`rate_limit.py`) y `AuthThrottleService` — Redis ya es una dependencia real en este repo (no solo mencionada en docs), usada hoy por rate limiting y auth throttle, pero siempre opcional con fallback a memoria:

- `InMemoryPermissionCache`: diccionario con TTL (`PERMISSIONS_CACHE_TTL_SECONDS`, por defecto 60s — dentro del rango 30-120s que sugiere la auditoría), thread-safe.
- `RedisPermissionCache`: mismo contrato, para cuando haya varias réplicas del backend (`PERMISSIONS_CACHE_BACKEND=redis`); cae a memoria automáticamente si `REDIS_URL` no está configurada.
- Clave: `(user_id, project_id)`. Valor cacheado: `(role_id | None, frozenset[permisos])`.

### El detalle que casi rompe la auditoría/regresión: qué hacer con el `assignment` devuelto

`get_project_permissions` devuelve una tupla `(assignment, permissions)`. De los 3 puntos del código que llaman esta función directamente, 2 (dentro del propio `permissions.py`) descartan `assignment` — pero **`approval_flow_service.user_can_execute_step` sí lo usa**, específicamente `assignment.role_id`, para verificar que el usuario tiene el rol exacto configurado como aprobador de un paso del flujo (`step.approver_role_id`). La primera versión de este cambio devolvía `None` incondicionalmente en un cache-hit (asumiendo, incorrectamente, que nadie leía el valor) — eso rompió la aprobación jurídica de doble-firma en `test_approval_flows.py` (un usuario podía aprobar una vez, pero el segundo intento de un *segundo* aprobador fallaba con 403 en vez del 400 esperado de "ya aprobado"). Se corrigió cacheando también el `role_id` y reconstruyendo, en un hit, un sustituto liviano (`CachedProjectAssignment`, un dataclass con solo ese campo) en vez de la fila ORM real — que de todos modos no sobrevive fuera de la sesión de BD que la cargó. Se agregó una prueba de regresión específica (`test_get_project_permissions_hits_cache_on_second_call_...`) que verifica el `role_id` en un hit de cache, no solo los permisos.

### Invalidación

La investigación del código mostró que hoy `UserProjectAssignment` y `UserOrganizationAssignment` **solo se crean, nunca se actualizan ni se borran** (no existe endpoint PATCH/DELETE para ninguna asignación, ni para editar los permisos de un `Role` existente). Por eso la única invalidación necesaria hoy es: al crear una asignación nueva (`assignment_service.create_assignment`/`create_organization_assignment`, que también cubre la carga masiva de asignaciones de docs/103 porque reutiliza el mismo servicio), invalidar todo lo cacheado de ese usuario — evita que una denegación cacheada justo antes de la asignación siga vigente hasta que expire el TTL. Si en el futuro se agrega edición de roles o revocación de asignaciones, esos puntos también necesitarán invalidar.

## Pruebas

`backend/tests/test_permission_cache.py` (10 pruebas nuevas): hit/miss básico del cache en memoria; expiración por TTL (con reloj simulado, sin depender de tiempo real); TTL en 0 desactiva el cache; `invalidate_user` solo afecta a ese usuario; fallback a memoria cuando `PERMISSIONS_CACHE_BACKEND=redis` sin `REDIS_URL`; formato de clave/serialización de `RedisPermissionCache` contra un stub (sin depender de Redis real); `get_project_permissions` realmente usa el cache en la segunda llamada (se cambia el permiso subyacente en la BD sin invalidar, y el segundo llamado sigue viendo el valor cacheado); el `role_id` se preserva correctamente en un hit; creación de asignación invalida el cache y dos peticiones HTTP reales (`POST /runtime/save`, denegada y luego permitida) demuestran el efecto inmediato sin esperar el TTL.

Se agregó `backend/tests/conftest.py` (no existía ningún `conftest.py` en el proyecto) con una fixture `autouse` que limpia el cache antes y después de cada prueba — necesario porque el cache es un singleton a nivel de módulo que persistiría durante toda la sesión de pytest, y muchas pruebas del proyecto reutilizan ids fijos por archivo (`"s001-user"`, `"orgtest-..."`, etc.).

Suite completa tras el cambio: 366 pasan (356 + 10 nuevas), mismos 5 errores preexistentes y ya documentados (bloqueo de `.pytest_cache` en Windows, no relacionado).

## Verificación en vivo

Contra el backend y frontend reales de la demo: login con `admin@infomatt360.demo`, dashboard del proyecto (ejercita `get_project_permissions` en cada tarjeta/resumen), y la pantalla de administración de usuarios (`/admin/users`, protegida por `identity.users.manage`) — todo cargó correctamente con el cache activo, sin 403 ni 500 inesperados. `backend/.env` y `frontend/.env.local` se revirtieron tras la verificación.

## Lo que sigue bloqueado en la categoría C

E-001 (réplicas + balanceador), E-003 (PgBouncer) y las pruebas de capacidad de 3.000 usuarios/300.000 solicitudes simultáneas siguen sin poder ejecutarse en este repositorio: no hay proveedor de nube, CI/CD ni entorno de staging. También se detectó que la auditoría está desactualizada en un punto de observabilidad: `metrics_service.py` (commit `4282ecd`, anterior a esta auditoría) ya expone p50/p95/p99 por endpoint en formato Prometheus, algo que el documento listaba como pendiente.
