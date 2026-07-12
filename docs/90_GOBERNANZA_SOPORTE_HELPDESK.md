# Gobernanza, soporte y mesa de ayuda no-code

## Objetivo

Dar a coordinadores y al super-administrador tres herramientas para
gobernar, diagnosticar y restaurar el ecosistema desde la web sin requerir
soporte tecnico dedicado.

## Lo que dice la especificacion original

**5. Modulo Avanzado de Gobernanza, Soporte y Help Desk No-Code** —
"Diseñado especificamente para que los coordinadores y el super-
administrador puedan gobernar, diagnosticar y restaurar el ecosistema
completo desde la interfaz web sin poseer conocimientos tecnicos avanzados
ni requerir ingenieros de soporte dedicados", con tres capacidades:
**Purga y Reset Controlado de Entornos (Tenant Clean)**, **Contraseñas
Volatiles e Intermitentes (Time-Boxed Keys)** y **Mesa de Ayuda y
Ticketing Automatizado No-Code**.

## 5.1 Purga controlada de entornos (Tenant Clean)

### Reinterpretacion para el modelo de tenant logico

La especificacion original describe un `TRUNCATE` sobre "el esquema
aislado de esa organizacion" -- literal en una arquitectura de schema-per-
tenant fisico de PostgreSQL. InfoMatt360 usa un **tenant logico**
([docs/71_ORGANIZACIONES_TENANT_LOGICO.md](71_ORGANIZACIONES_TENANT_LOGICO.md)):
una sola base de datos, aislamiento por `project_id`/`organization_id` a
nivel de aplicacion. `governance_service.tenant_clean()`
(`backend/app/services/governance_service.py`) logra el mismo resultado
funcional: borra por `project_id`, para cada proyecto de la organizacion,
las filas de las tablas que se consideran "datos de prueba/operativos".

### Que se purga y que se protege

Se purgan (con `DELETE ... WHERE project_id IN (...)`): `Participant`,
`RuntimeRecord` + `RuntimeRecordValue`, `FileAsset`, `AiCheck`,
`OcrResult`, `ExecutiveAnalysis`, `ReviewAction`, `InternalMessage`,
`WhatsAppNotification`, `ExcelImportJob`, `BulkImportJob`,
`ManagerQrToken`.

Se protegen explicitamente (nunca se tocan): `User`,
`UserProjectAssignment`, `Role`, `Project`, `Organization`,
`OrganizationBranding`, `BuilderTemplate`, `ApprovalFlow`/`Step`,
`IntegrationSource`/`Map`, `MailProfile`, `StorageProfile`, `ApiKey`,
`AiAuditConfig`, `AuditLog`, `ScheduledTask`, `ReportDefinition`,
`FormTheme` -- y, de forma notable, **todo el modulo ERP**
(`ErpInventoryItem`, `ErpInventoryMovement`, `ErpPayrollEntry`) y
`IntegrationJob`: sus propios modelos se documentan en el codigo como
"ledger inmutable" (nunca se edita ni se borra una fila existente), asi
que tenant-clean respeta esa invariante en vez de romperla, ademas de
cumplir literalmente con "protegiendo las tablas de inventarios maestros"
de la especificacion.

### Accion critica: tres capas de confirmacion

`POST /api/v1/organizations/{organization_id}/tenant-clean` exige, en
este orden:

1. Permiso `organizations.tenant_clean` (nuevo, distinto de
   `organizations.manage` -- una organizacion puede administrarse sin
   poder purgarla).
2. Que la organizacion este entre las organizaciones a las que el usuario
   tiene acceso (via sus proyectos asignados).
3. Que `confirm_slug` en el body coincida exactamente con el slug de la
   organizacion.
4. Un codigo TOTP vigente del usuario (`mfa_service.verify_totp`, el mismo
   motor que el login con 2FA); si el usuario no tiene 2FA activado, la
   accion se rechaza de plano -- no hay forma de purgar sin 2FA.

Responde con el conteo de filas borradas por tabla
(`TenantCleanResult.deleted_counts`), para que el panel de administracion
pueda mostrar un resumen verificable de lo que se elimino.

## 5.2 Credenciales de emergencia time-boxed

Modelo `EmergencyAccessKey` (`backend/app/models/emergency_access.py`):
cubre "auditores de entes de control externos o gestores con bloqueos de
identidad en zonas rurales" emitiendo un codigo de un solo uso para una
cuenta de usuario **existente**, valido por un numero configurable de
horas (1-168, por defecto 24). El codigo nunca se guarda en texto plano
(solo su hash SHA-256, igual que `ManagerQrToken`).

- `POST /api/v1/emergency-access/keys` (permiso `identity.users.manage`,
  con acceso al proyecto): emite el codigo, lo devuelve **una sola vez**
  en la respuesta (`EmergencyAccessKeyIssued.code`); nunca vuelve a ser
  recuperable despues.
- `GET /api/v1/emergency-access/keys/project/{project_id}`: lista llaves
  sin exponer el codigo ni su hash.
- `POST /api/v1/emergency-access/keys/{id}/revoke`: invalida una llave
  antes de su vencimiento.
- `POST /api/v1/emergency-access/redeem` (semi-publico, con throttling por
  IP igual que `/enrollment/validate`): recibe el codigo, valida que no
  este usado, revocado ni vencido, y emite una sesion normal para el
  usuario asociado.

### Auto-destruccion real, no solo textual

`create_access_token()` (`backend/app/core/security.py`) ahora acepta un
`expires_delta` opcional (retrocompatible: los tres call sites existentes
en `auth_service.py` no lo usan y siguen igual). El token emitido al
canjear una llave de emergencia expira en el tiempo **restante** del
time-box, nunca en la duracion normal de sesion configurada -- si al
usuario le quedaban 3 horas de la llave de 24, su sesion dura 3 horas, no
el `access_token_expire_minutes` habitual. Esto cumple literalmente "el
motor backend invalida el hash criptografico automaticamente, auto-
destruyendo el acceso sin necesidad de mantenimiento manual": el acceso
se autolimita incluso si el usuario nunca cierra sesion.

## 5.3 Mesa de ayuda y ticketing automatizado no-code

Modelo `SupportTicket` (`backend/app/models/support.py`) y motor de reglas
semanticas por palabras clave en `support_service.py` (arbol de decision
simple, sin LLM):

1. Si la descripcion contiene senales de **daño fisico** del dispositivo
   (pantalla rota, no enciende, se cayo, se mojo, etc.), el ticket
   **siempre** se escala a soporte humano, sin importar que otras palabras
   coincidan (una tablet con pantalla rota que "no sincroniza" no recibe
   el tutorial de sincronizacion -- va directo a un humano).
2. Si no, se compara contra un catalogo de patrones conocidos
   (`AUTO_RESPONSE_RULES`: sincronizacion, GPS/ubicacion, camara, inicio de
   sesion); de coincidir, el ticket se marca `auto_resolved` con el
   tutorial correspondiente, sin intervencion humana.
3. Si no coincide con nada conocido, se escala a soporte humano por no
   reconocer el patron.

Endpoints (`backend/app/api/v1/support.py`, prefijo `/api/v1/support`):

| Metodo | Ruta | Permiso |
| --- | --- | --- |
| `POST` | `/tickets` | Acceso al proyecto (`records.write` o `support.tickets.manage`) -- lo reporta cualquier gestor de campo |
| `GET` | `/tickets/project/{project_id}` | Acceso al proyecto |
| `POST` | `/tickets/{ticket_id}/resolve` | `support.tickets.manage` |

## Permisos nuevos

`organizations.tenant_clean` y `support.tickets.manage` (ver
[docs/60_CATALOGO_PERMISOS.md](60_CATALOGO_PERMISOS.md)). Emitir/revocar
llaves de emergencia reutiliza `identity.users.manage` -- es
fundamentalmente una accion de administracion de identidad, no una
capacidad nueva.

## Pruebas

- `backend/tests/test_governance_tenant_clean.py`: rechazo sin permiso,
  sin afiliacion a la organizacion, con slug incorrecto o TOTP invalido;
  purga exitosa con conteos correctos; verifica que el modulo ERP y
  `IntegrationJob` quedan intactos, que otra organizacion no se toca, y
  que el mismo codigo TOTP no se puede reutilizar (replay).
- `backend/tests/test_emergency_access.py`: permiso requerido para emitir,
  el codigo se devuelve una sola vez y nunca se expone despues, el canje
  otorga una sesion valida para el usuario correcto y es de un solo uso,
  rechazo de llaves vencidas o revocadas, rechazo de codigos desconocidos.
- `backend/tests/test_support_tickets.py`: acceso al proyecto requerido
  para crear tickets, auto-resolucion por palabras clave (sync, GPS), daño
  fisico siempre escala a humano aunque coincida con otro patron,
  descripciones no reconocidas escalan a humano, y solo
  `support.tickets.manage` puede resolver un ticket escalado.

## Pantalla en el frontend

`frontend/src/modules/admin/GovernanceApp.tsx` (ruta `/admin/governance`,
visible en el menu si el usuario tiene al menos uno de
`organizations.tenant_clean`, `identity.users.manage` o
`support.tickets.manage`), con tres pestañas -- cada una solo se muestra si
el usuario tiene el permiso correspondiente:

- **Purga de organización**: formulario con `organization_id`,
  `confirm_slug` y codigo 2FA; el boton "Ejecutar purga" pide una
  confirmacion adicional del navegador (`window.confirm`) antes de llamar
  al endpoint, como capa extra de proteccion sobre las ya existentes en el
  backend (permiso + membresia + slug + 2FA). Muestra el conteo de filas
  borradas por tabla al terminar.
- **Credenciales de emergencia**: formulario para emitir (usuario, horas de
  vigencia, proposito) con el codigo mostrado una sola vez; lista de
  credenciales del proyecto activo con boton "Revocar" (oculto en llaves ya
  usadas o revocadas).
- **Mesa de ayuda**: formulario para reportar una falla (asunto +
  descripcion), con el resultado de la clasificacion automatica mostrado de
  inmediato (auto-resuelto con el tutorial, o escalado a humano); lista de
  tickets del proyecto con filtro por estado y boton "Marcar resuelto" para
  los tickets abiertos.

Cliente API en `frontend/src/modules/admin/governanceApi.ts`. Verificado en
navegador real: emision y revocacion de una credencial de emergencia
reflejadas de inmediato en la lista, y un ticket con la palabra
"sincronizacion" auto-resuelto mostrando el tutorial exacto del motor de
reglas.

## Limites conocidos

- Sin selector de organizaciones en la pestaña de purga: el ID se escribe
  a mano, ya que la gestion de organizaciones en si tampoco tiene pantalla
  propia todavia (se crean via Swagger/API desde el instalador o
  `POST /api/v1/organizations/`).
- El motor de reglas de la mesa de ayuda es un arbol de decision por
  palabras clave literal (no usa el LLM de la auditoria semantica); frases
  que no contienen ninguna de las palabras clave configuradas siempre
  escalan a humano, incluso si el problema es en realidad conocido.
- Tenant-clean no ofrece "deshacer": es una eliminacion real e inmediata,
  sin papelera de reciclaje. Se recomienda tomar un backup
  (`docs/78_BACKUPS_PROGRAMABLES_WEB.md`) antes de ejecutarla en un
  entorno con datos que pudieran ser necesarios.
