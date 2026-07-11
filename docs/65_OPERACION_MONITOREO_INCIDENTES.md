# Operacion, monitoreo e incidentes

## Objetivo

Definir una rutina minima para operar InfoMatt360 despues del despliegue:
verificar salud, detectar fallos temprano y responder incidentes con evidencia.

## Monitor liviano

Para monitoreo simple desde consola, servidor o tarea programada:

```powershell
.\scripts\monitor-health.cmd `
  -BackendUrl https://api.tu-dominio.com `
  -FrontendUrl https://app.tu-dominio.com `
  -IntervalSeconds 60 `
  -FailureThreshold 3
```

El monitor valida:

- `/health`;
- `/api/v1/health/ready`;
- frontend;
- latencia aproximada;
- fallos consecutivos.

Si alcanza el umbral de fallos consecutivos, termina con codigo `2` y escribe
una linea `ALERT` para integrarse con tareas programadas o recolectores de logs.

## Rutina diaria recomendada

- Revisar `/api/v1/health/ready`.
- Revisar `/admin/metrics`.
- Revisar `/admin/bulk-jobs`.
- Confirmar que no hay crecimiento sostenido de `5xx` o `429`.
- Confirmar que no hay jobs bulk atascados.
- Confirmar que backups recientes existen.
- Revisar almacenamiento de `UPLOAD_DIRECTORY`.
- Revisar logs por errores repetidos y `X-Request-ID`.

## Senales de alerta

- `ready` devuelve `not_ready`.
- Suben errores `5xx`.
- Suben `429` sin explicacion de integraciones esperadas.
- Aumentan `failed_jobs`, `failed_stale` o `retries_scheduled`.
- El worker bulk deja de procesar ciclos.
- Latencia p95/p99 crece de forma sostenida.
- Login, MFA o recuperacion de contrasena empiezan a fallar.
- SMTP deja de enviar correos.
- Disco de PostgreSQL o uploads se acerca al limite.

## Triage inicial

1. Buscar `X-Request-ID` del fallo.
2. Revisar logs del backend.
3. Revisar `/admin/metrics`.
4. Revisar `/admin/bulk-jobs`.
5. Confirmar si hay despliegue reciente.
6. Confirmar si hay integracion externa enviando volumen anormal.
7. Si afecta datos o migraciones, consultar `docs/64_ROLLBACK_OPERATIVO.md`.

## Clasificacion rapida

- Severidad 1: API caida, base caida, login general caido, perdida de datos o integraciones criticas bloqueadas.
- Severidad 2: modulo importante degradado, bulk jobs fallando, reportes/mapas no disponibles.
- Severidad 3: error puntual, usuario aislado, alerta recuperable o tarea administrativa.

## Evidencia minima de incidente

- Fecha y hora.
- Usuario/proyecto afectado.
- Endpoint o modulo afectado.
- `X-Request-ID`.
- Captura de `/admin/metrics` o salida de Prometheus.
- Estado de `/api/v1/health/ready`.
- Logs backend/worker.
- Version del paquete o SHA256 desplegado.
- Accion tomada: mitigacion, rollback, restore, reintento o correccion.

## Cierre

Antes de cerrar un incidente:

- health/readiness estable;
- sin crecimiento nuevo de `5xx`;
- worker bulk procesando;
- integraciones reanudadas;
- usuarios afectados informados;
- causa probable documentada;
- accion preventiva definida.
