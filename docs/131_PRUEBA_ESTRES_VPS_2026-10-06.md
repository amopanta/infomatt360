# Prueba de carga controlada en el VPS — 6 de octubre de 2026

## Alcance

Se enviaron solicitudes HTTPS al sitio productivo desde el propio VPS, con 80 % a `GET /api/v1/health/ready` y 20 % a `GET /`. Ambas rutas son de lectura; la primera comprueba base de datos, Redis y disponibilidad del servicio. No se cambiaron datos, credenciales ni límites de tasa. El generador utilizó conexiones persistentes por hilo, 64 hilos como máximo y fases de 15 segundos con 5, 20, 50 y 100 solicitudes objetivo por segundo. El script detenía la rampa si una fase superaba 1 % de respuestas distintas de 200 o p95 de 2 segundos.

El VPS tenía 4 CPU, 7,9 GiB de RAM, sin swap, dos réplicas de API, PgBouncer, PostgreSQL y Redis. La prueba se ejecutó después del despliegue `5ebdbe9`.

## Resultados

| Objetivo | Solicitudes | Tasa real | HTTP 200 | p50 | p95 | p99 | Máximo |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 5/s | 75 | 5,06/s | 75 | 26 ms | 74 ms | 84 ms | 89 ms |
| 20/s | 300 | 20,02/s | 300 | 23 ms | 52 ms | 70 ms | 89 ms |
| 50/s | 750 | 49,46/s | 750 | 53 ms | 1.277 ms | 1.704 ms | 1.935 ms |
| 100/s | 1.500 | 86,96/s | 1.500 | 594 ms | 1.059 ms | 1.248 ms | 1.388 ms |

Total: **2.625 solicitudes, 0 errores HTTP o de red**. La fase de 100/s entregó 86,96/s; este resultado incluye el límite del generador Python y del propio VPS, por lo que no se interpreta como capacidad máxima certificada. El p95 de 50/s tuvo un pico que no se repitió en 100/s; requiere una corrida más larga y observabilidad por ruta para atribuir su causa.

Durante la rampa, las dos API siguieron activas y se observaron alrededor de 52 % y 61 % de CPU por contenedor en una muestra. Después, ambas réplicas quedaron `healthy`, `/api/v1/health/ready` respondió 200, la memoria disponible fue ~4,2 GiB y no aparecieron `Traceback`, `QueuePool`, `TimeoutError` ni errores de PostgreSQL en los registros revisados de los últimos cinco minutos.

## Límites y siguiente prueba

Esta prueba **no** cubre captura, búsqueda de registros autenticada, sincronización de lotes, exportaciones ni 3.000 usuarios concurrentes. Para medir esos flujos se requiere una cuenta y un proyecto de pruebas activos, una mezcla representativa de formularios y participantes, y un generador externo al VPS que no compita por sus CPU. Las escrituras deben ir a datos de prueba identificables. La rampa deberá monitorear latencia por ruta, p95/p99, tasa de errores, CPU, PgBouncer y PostgreSQL, y detenerse ante degradación sostenida.

Datos brutos de esta corrida: `stress-results-20261006.jsonl` en el espacio de trabajo de la tarea. Generador: `stress_readonly_20261006.py` en el mismo lugar.
