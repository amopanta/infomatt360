# API de lectura para sistemas externos

## Objetivo

Complementar el push saliente ([86_INTEROPERABILIDAD_DONANTES.md](86_INTEROPERABILIDAD_DONANTES.md))
con la direccion opuesta: que un sistema externo (una base de datos, un
panel de BI, el sistema de un donante) pueda **consultar** datos de
InfoMatt360 cuando quiera, sin que InfoMatt360 tenga que iniciar nada.

## Contexto: por que existen dos documentos separados

Al construir la interoperabilidad con ActivityInfo/TolaData se aclaro que
la referencia a esas plataformas en la especificacion original no era
"conectate literalmente a esas dos plataformas": era la inspiracion de que
un sistema de gestion territorial serio necesita **ambas direcciones** de
intercambio de datos con el exterior:

1. **Salida por evento** (push) — cuando algo pasa en InfoMatt360 (se
   aprueba un registro), el sistema avisa proactivamente. Cubierto en
   [86_INTEROPERABILIDAD_DONANTES.md](86_INTEROPERABILIDAD_DONANTES.md).
2. **Salida por consulta** (pull) — un sistema externo pregunta cuando
   quiere. Cubierto aqui.

Ninguno de los dos asume el esquema exacto de ActivityInfo o TolaData
(no verificable sin una cuenta real de esas plataformas): son capacidades
genericas que cualquier sistema externo puede usar, incluyendo esas dos
plataformas si se configuran para consumirlas.

## Reutilizacion total de lo existente

Esta API no introduce logica de negocio nueva. Es una capa de autenticacion
distinta (API key en vez de sesion de usuario) sobre servicios que ya
usan las pantallas internas:

| Endpoint | Reutiliza | Permiso requerido |
| --- | --- | --- |
| `GET /api/v1/external-api/records` | `runtime_record_service.search_template_records()` (el mismo motor de busqueda paginada que usa el buscador interno de registros) | `records.read` |
| `GET /api/v1/external-api/participants` | `participant_service.list_participants()` | `records.read` |
| `GET /api/v1/external-api/summary` | `report_service.project_summary()` (el mismo resumen que alimenta el panel de reportes interno) | `reports.export` |

Los permisos (`records.read`, `reports.export`) son los mismos del
catalogo central (`app.core.permissions`) que ya usan los roles de
usuario — `require_api_key_permission` verifica el mismo nombre de
permiso sobre la lista que tiene asignada la API key, sin necesitar
permisos nuevos ni duplicados.

## Autenticacion

Igual que `POST /runtime/bulk/save` (unico endpoint que ya usaba API key
antes de esta fase): header `X-API-Key`, gestionado desde
`POST /api/v1/api-keys/` (ver [53_SEGURIDAD_API_KEYS.md](53_SEGURIDAD_API_KEYS.md)).
La API key queda ligada a un solo proyecto; todos los endpoints devuelven
solo datos de ese proyecto (`api_key.project_id`), sin parametro de
proyecto en la URL.

## Detalles por endpoint

- **`GET /records?template_id=...&status=approved&limit=25&offset=0`** —
  por defecto solo devuelve registros `approved` (lo relevante para un
  donante externo); pasar `status=` vacio devuelve todos los estados.
  Rechaza con `403` si `template_id` no pertenece al proyecto de la API
  key.
- **`GET /participants`** — todos los participantes del proyecto, sin
  paginar (ver limite conocido abajo).
- **`GET /summary`** — el mismo resumen agregado (conteos por estado,
  etc.) que usa el panel de reportes interno.

## Limites conocidos

- `GET /participants` no pagina todavia; en un proyecto con muchos miles
  de participantes esto puede ser una respuesta grande.
- `GET /records` exige `template_id`: un partner externo debe conocer el
  identificador de la plantilla que le interesa (no hay un endpoint de
  "todos los registros del proyecto sin importar plantilla").
- Sin webhooks de "hay datos nuevos"; el sistema externo debe consultar
  periodicamente (polling) si quiere detectar cambios, o usar el push de
  la doc 86 si prefiere ser notificado.
