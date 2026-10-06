# Prueba distribuida de lectura — 6 de octubre de 2026

## Método

Dos generadores ejecutaron simultáneamente `loadtest/distributed_read_probe.py` durante 20 segundos contra el dominio productivo. Uno corrió en el VPS a 50 solicitudes objetivo por segundo y otro desde el equipo externo a 10/s. Cada uno distribuyó 80 % de solicitudes a `GET /api/v1/health/ready` y 20 % a `GET /`. El script mantiene conexiones HTTPS por hilo, limita los hilos a 48 y no modifica datos ni configuración.

Los agentes de apoyo inspeccionaron los escenarios de carga autenticada y el protocolo de observación. No generaron solicitudes adicionales: la ejecución de carga quedó bajo un solo coordinador para conservar el límite total previsto.

| Origen | Objetivo | Solicitudes | Tasa real | HTTP 200 | p50 | p95 | p99 |
|---|---:|---:|---:|---:|---:|---:|---:|
| VPS | 50/s | 1.000 | 49,88/s | 1.000 | 23 ms | 109 ms | 305 ms |
| Externo | 10/s | 200 | 9,94/s | 200 | 192 ms | 267 ms | 570 ms |

**Total: 1.200 solicitudes, 0 errores.** En la ruta de salud, el p95 fue 127 ms desde el VPS y 267 ms desde fuera. En la portada fue 14 ms y 186 ms, respectivamente. La diferencia entre orígenes incluye la latencia de red y no debe atribuirse toda al servidor.

Al finalizar, ambas réplicas de API estaban `healthy`, la ruta de salud respondió 200, había ~4,1 GiB de memoria disponible y los registros revisados de ambas API no contenían `Traceback`, `QueuePool`, `TimeoutError` ni `ERROR` en los últimos tres minutos.

## Alcance pendiente

Esta prueba confirma la atención simultánea de dos orígenes en rutas públicas de lectura. No mide sesiones autenticadas, creación de registros, sincronización de lotes, exportaciones ni 3.000 usuarios. Para esos flujos se necesitan una cuenta y un proyecto de pruebas con formularios, participantes y permisos activos. La prueba siguiente debe mezclar búsquedas, captura, lotes de 5–20 respuestas y exportación, registrar IDs e idempotencia, vigilar PgBouncer/PostgreSQL y detenerse ante errores >1 % o p95 sostenido >2 s. Los datos creados deben ser identificables y limpiarse al terminar.
