# Interoperabilidad con plataformas de donantes (ActivityInfo / TolaData) -- salida por evento (push)

## Objetivo

Al aprobarse un registro, enviarlo automaticamente a la plataforma de
seguimiento de un donante internacional (ActivityInfo, TolaData u otra),
eliminando la digitacion manual para reportar avances.

**Esta es solo una de las dos direcciones de interoperabilidad**: este
documento cubre la salida por evento (push, InfoMatt360 avisa). Para la
salida por consulta (pull, el sistema externo pregunta cuando quiere), ver
[87_API_LECTURA_EXTERNA.md](87_API_LECTURA_EXTERNA.md).

## Adaptacion respecto al documento original

La especificacion original describe un modulo que "mapea y traduce
estructuralmente a las columnas y hashes requeridos por las plataformas
globales de donantes (ActivityInfo o TolaData), inyectando el registro
mediante llamadas REST". No existen esquemas publicos y estables de esas
APIs verificables sin una cuenta real: cada organizacion tiene su propia
base de datos/columnas configuradas en ActivityInfo o TolaData. Por eso
este modulo es un **conector saliente generico y configurable** (URL base
+ credenciales + mapeo de campos), apuntable a cualquiera de las dos
plataformas -- o a otra distinta -- segun como se configure, en vez de un
cliente que asuma un esquema fijo que podria no calzar con la cuenta real
del usuario.

## Modelos reutilizados (no nuevos)

Estos modelos ya existian como documentacion retroactiva sin
comportamiento real (CRUD sin logica de envio). Esta fase los completa en
vez de crear modelos paralelos:

- `IntegrationSource` (`backend/app/models/integrations.py`) — conexion a
  un sistema externo: `base_url`, `config_json` (config no secreta),
  `credentials_encrypted` (API key/token cifrado con Fernet, igual que los
  tokens OAuth de Google Drive -- nunca se expone en `IntegrationSourceRead`,
  solo un booleano `has_credentials`).
- `IntegrationMap` — mapeo de campos de una plantilla hacia el esquema del
  sistema externo. Gana `template_id`: vincula el mapeo a un formulario
  del Builder para que el disparo automatico sepa que registros enviar.
  `fields_json` es un diccionario `{ "campo_del_formulario": "columna_destino" }`.
- `IntegrationJob` — ledger inmutable de intentos de envio. Gana
  `reference_record_id` para trazar que registro origino cada intento.

## Disparador

Mismo punto que ERP y WhatsApp: dentro de `review_service.apply_action()`,
al aprobar un `RuntimeRecord`, se llama
`integration_service.push_approved_record(db, record)`. Si la plantilla no
tiene un `IntegrationMap` activo, no hace nada (no-op silencioso). Si lo
tiene:

1. Busca la `IntegrationSource` del mapeo.
2. Traduce los valores del registro (`RuntimeRecordValue`) segun
   `fields_json`.
3. Envia `POST {source.base_url}` con el payload mapeado y
   `Authorization: Bearer {credenciales descifradas}` si hay credenciales.
4. Registra el resultado en `IntegrationJob` (`sent`/`failed`).

**Nunca bloquea la aprobacion**: a diferencia del motor ERP (que si
bloquea si el stock es insuficiente, ver
[84_ERP_HEADLESS_INVENTARIO_NOMINA.md](84_ERP_HEADLESS_INVENTARIO_NOMINA.md)),
un donante externo caido o mal configurado no debe impedir que el equipo
apruebe su trabajo interno -- se comporta igual que WhatsApp/WAHA
(fire-and-forget, con ledger para diagnosticar despues).

## Endpoints (`backend/app/api/v1/integrations.py`, prefijo `/api/v1/integrations`)

Todos requieren el permiso `integrations.donor_sync.manage` sobre el
proyecto (resuelto via el proyecto de la fuente para `maps`/`jobs`). Antes
de esta fase, `create_map` y `create_job` no verificaban ningun permiso ni
acceso al proyecto -- se corrigio como parte de completar el modulo.

| Metodo | Ruta |
| --- | --- |
| `POST` / `GET` | `/sources`, `/sources/{project_id}` |
| `POST` / `GET` | `/maps`, `/maps/{source_id}` |
| `POST` / `GET` | `/jobs`, `/jobs/{source_id}` |

## Como activarlo con una cuenta real

1. Crear la fuente: `POST /integrations/sources` con `source_type` (`activityinfo` o `toladata`, informativo), `base_url` (endpoint real que expone tu cuenta) y `credentials` (API key/token real de tu cuenta -- se cifra al guardar).
2. Crear el mapeo: `POST /integrations/maps` con `source_id`, `template_id` (la plantilla del Builder que representa el formulario a reportar) y `fields_json` (diccionario campo-del-formulario → columna que espera tu base de ActivityInfo/TolaData).
3. Aprobar un registro de esa plantilla — el envio ocurre automaticamente.

## Limites conocidos

- Sin pantalla propia en el frontend todavia (se opera por Swagger/API directa).
- No hay reintento automatico de envios fallidos; el ledger (`IntegrationJob`) permite identificarlos para reintento manual.
- Solo push saliente al aprobar; no hay sincronizacion bidireccional ni consulta de estado desde la plataforma del donante.
- El payload es un `POST` JSON simple con `Authorization: Bearer`; si la cuenta real exige un esquema de autenticacion distinto (OAuth, firma HMAC, etc.), se debe extender `integration_service.push_approved_record` para ese caso especifico.
