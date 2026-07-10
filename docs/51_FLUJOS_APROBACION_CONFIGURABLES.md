# Flujos de aprobacion configurables

## Objetivo

Permitir que un proyecto o formulario defina sus propios pasos de aprobacion sin tocar codigo.

Si no hay flujo configurado activo, InfoMatt360 usa el flujo predeterminado:

```text
submitted -> under_review -> tech_approved -> coordinator_approved -> approved
```

## Modelo

```text
approval_flows
- project_id
- template_id opcional
- name
- description
- flow_version
- status

approval_flow_steps
- flow_id
- step_order
- name
- action_label
- action
- status_after
- required_permission
- approver_user_id opcional
- approver_role_id opcional
- require_all
- status
```

## Resolucion del flujo

El backend busca el flujo activo en este orden:

1. flujo especifico del formulario (`template_id`);
2. flujo general del proyecto;
3. flujo predeterminado en codigo.

## Endpoints

```text
POST /api/v1/approval-flows/
GET /api/v1/approval-flows/{project_id}
GET /api/v1/approval-flows/detail/{flow_id}
POST /api/v1/approval-flows/steps
GET /api/v1/review/records/{record_id}/next-actions
GET /api/v1/review/records/{record_id}/approval-progress
GET /api/v1/review/records/{record_id}/flow-comparison
```

## Panel administrativo

El frontend incluye un panel en:

```text
/admin/approval-flows
```

Desde este panel el administrador puede:

- listar flujos configurados del proyecto;
- filtrar flujos por `template_id`;
- crear un flujo general del proyecto o especifico de un formulario;
- abrir el detalle de un flujo;
- editar nombre, descripcion, formulario asociado y estado activo/inactivo del flujo;
- agregar pasos de aprobacion con accion, estado resultante, permiso requerido y aprobador opcional;
- editar pasos existentes: orden, nombre, texto del boton, accion tecnica, estado resultante, permiso requerido, usuario/rol aprobador, regla `require_all` y estado;
- desactivar o reactivar pasos sin borrar el historico;
- usar plantillas rapidas para pasos frecuentes como aprobacion tecnica, coordinador, devolucion, rechazo y aprobacion final.

El panel de Registros consume `/review/records/{record_id}/next-actions`, por lo que al existir un flujo activo el usuario ve las acciones configuradas sin despliegue adicional de codigo.

## Permisos

Crear flujos y pasos requiere:

```text
records.approve
```

Ejecutar un paso configurado requiere:

- pertenecer al proyecto;
- tener el permiso definido en `required_permission`;
- coincidir con `approver_user_id`, si fue definido;
- coincidir con `approver_role_id`, si fue definido.

## Aprobacion multiple con `require_all`

Cuando un paso tiene:

```text
require_all: true
approver_role_id: <rol>
```

InfoMatt360 exige que todos los usuarios activos del proyecto con ese rol ejecuten la misma aprobacion antes de cambiar el estado del registro.

Comportamiento:

- cada aprobador requerido genera una entrada en el historial de revision;
- el primer aprobador no mueve todavia el estado del registro;
- el sistema evita aprobaciones duplicadas del mismo usuario para el mismo paso;
- cuando aprueba el ultimo usuario requerido, el registro avanza al `status_after` del paso;
- si el rol no tiene usuarios activos, el paso se comporta como aprobacion simple para no bloquear accidentalmente el flujo.

El panel de Registros muestra una tarjeta de "Aprobacion parcial" cuando un paso multiple esta en curso, con:

- total de aprobadores requeridos;
- aprobadores que ya completaron;
- aprobadores pendientes;
- estado destino del paso.

## Versionamiento y trazabilidad

Cada flujo tiene un `flow_version` incremental.

La version aumenta cuando:

- se edita el flujo;
- se edita, activa o desactiva un paso.

Cada accion de revision guarda:

- `approval_flow_id`;
- `approval_flow_version`.

Esto permite auditar con que version del flujo se ejecuto una aprobacion, incluso si posteriormente el administrador cambia los pasos o aprobadores.

## Snapshot de flujo por registro

Cuando se crea un registro Runtime, InfoMatt360 guarda en la cabecera:

- `approval_flow_id`;
- `approval_flow_version`;
- `approval_flow_snapshot_json`.

Ese snapshot conserva los pasos activos del flujo en ese momento. Las acciones futuras de revision consultan primero el snapshot del registro; si existe, el registro sigue usando esas reglas aunque el administrador edite, active o desactive pasos despues.

Esto evita que un proceso ya iniciado cambie sus aprobadores a mitad de camino.

El panel de Registros incluye una comparacion visual entre:

- snapshot historico guardado en el registro;
- flujo actual configurado para el proyecto/formulario.

Si ambos difieren, la tarjeta se marca como cambiada para que el usuario entienda que ese registro sigue un flujo historico.

La comparacion tambien expone diferencias campo por campo:

- version;
- nombre del flujo;
- cantidad de pasos;
- pasos agregados o eliminados;
- nombre, texto del boton, accion tecnica, estado destino, permiso, usuario/rol aprobador, `require_all` y estado de cada paso.

## Ejemplo

Un proyecto puede crear un flujo:

```text
Paso 1: Revision juridica
  status_after: legal_approved
  required_permission: records.legal
  approver_user_id: usuario-juridico

Paso 2: Aprobacion financiera
  status_after: finance_approved
  required_permission: records.finance

Paso 3: Aprobacion final
  status_after: approved
  required_permission: records.approve
```

El panel de Registros consulta `/next-actions`, por lo que puede mostrar acciones configuradas sin cambiar el frontend.

## Pendientes

- vista expandida con resaltado visual por columna para cada diferencia.
