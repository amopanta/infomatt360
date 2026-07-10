# Runbook funcional del administrador

## Objetivo

Guiar al administrador de proyecto en las tareas operativas que se pueden hacer
desde la interfaz, sin tocar codigo ni base de datos.

## Acceso inicial

1. Iniciar sesion con usuario administrador.
2. Seleccionar el proyecto activo en la parte superior si el usuario pertenece
   a varios proyectos.
3. Verificar que el menu muestre solo las opciones permitidas por el rol.

## Usuarios y seguridad

Ruta:

```text
/admin/users
```

Tareas disponibles:

- corregir correo de un usuario;
- reiniciar contrasena temporal;
- forzar cambio de contrasena al siguiente ingreso;
- reiniciar MFA si el usuario perdio el autenticador;
- invalidar sesiones previas como parte del reinicio.

Buenas practicas:

- confirmar la identidad del usuario antes de reiniciar credenciales;
- entregar contrasenas temporales por canal seguro;
- pedir al usuario activar MFA si su rol es sensible;
- revisar auditoria despues de operaciones sensibles.

## Flujos de aprobacion

Ruta:

```text
/admin/approval-flows
```

Tareas disponibles:

- crear flujo por proyecto/formulario;
- agregar pasos de aprobacion;
- definir permiso requerido;
- asignar aprobador por usuario o rol;
- activar o desactivar pasos;
- versionar cambios sin romper registros historicos.

Recomendacion:

- probar primero con un registro de muestra;
- documentar quien aprueba cada paso;
- evitar dejar pasos sin aprobadores reales;
- revisar el panel de registros para confirmar las acciones disponibles.

## API keys e integraciones

Ruta:

```text
/admin/api-keys
```

Tareas disponibles:

- crear API key para integraciones;
- asignar permisos;
- elegir perfil de rate limit;
- revocar claves.

Buenas practicas:

- usar una API key por sistema externo;
- no compartir una misma clave entre proveedores;
- copiar el secreto completo solo al crearlo, porque no vuelve a mostrarse;
- usar `trusted_sync` o `high_volume` solo para integraciones confiables y auditadas;
- revocar claves no usadas.

## Sincronizacion bulk

Ruta:

```text
/admin/bulk-jobs
```

Tareas disponibles:

- ver lotes recibidos;
- filtrar por estado o formulario;
- revisar worker, heartbeat, intentos y proximo reintento;
- procesar manualmente un lote en cola;
- exportar errores CSV;
- detectar posibles atascados.

Si un lote falla:

1. abrir el detalle;
2. revisar `last_error`;
3. exportar errores CSV si hay items fallidos;
4. corregir datos en el sistema externo;
5. reenviar con una nueva `idempotency_key` si el payload cambia.

## Metricas operativas

Ruta:

```text
/admin/metrics
```

Revisar:

- errores `5xx`;
- respuestas `429`;
- errores `401/403`;
- latencia p95/p99;
- rutas con mas trafico;
- jobs bulk fallidos o reintentados.

Si aparecen alertas:

- buscar el `X-Request-ID` del evento;
- revisar logs del backend;
- revisar si coincide con una integracion externa;
- consultar `docs/65_OPERACION_MONITOREO_INCIDENTES.md`.

## Auditoria

Ruta:

```text
/audit
```

Usar para:

- confirmar cambios sensibles;
- revisar operaciones administrativas;
- validar acciones de seguridad;
- reconstruir eventos por usuario/proyecto.

## Reglas de oro

- No crear usuarios genericos compartidos.
- No entregar claves por chat inseguro.
- No usar la API key de una integracion para otra.
- No cambiar flujos activos sin avisar a los aprobadores.
- No procesar manualmente jobs bulk sin entender el error.
- Ante duda, revisar metricas, auditoria y logs por `X-Request-ID`.
