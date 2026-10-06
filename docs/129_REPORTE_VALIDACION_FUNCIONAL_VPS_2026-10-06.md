# Reporte de validación funcional de InfoMatt360 en el VPS

**Fecha:** 6 de octubre de 2026  
**Sitio:** https://infomatt360.tecnomatt.com  
**Repositorio desplegado:** `amopanta/infomatt360`, `main` en `3c2fb3d` (último cambio de documentación); código de la aplicación construido desde `0c01079`.  
**Alcance:** inspección de producción de solo lectura y pruebas automatizadas del código desplegado en contenedores temporales. No se crearon ni modificaron datos de producción.

## Resultado ejecutivo

El sitio responde por HTTPS, los dos backend y la base de datos están saludables y la migración aplicada coincide con la última del repositorio (`0078_gestor_teams`). La batería automatizada terminó con **486/486 pruebas del backend, 105/105 del frontend y 17/17 del escritorio aprobadas**. Esto acredita los casos codificados en esas pruebas; no equivale a haber ejecutado cada flujo de negocio con una sesión real en el navegador.

En los datos de producción hay tres hallazgos que requieren atención operativa: las **41 asignaciones de participantes** están asociadas a formularios eliminados; **5 de 9 registros** carecen de participante enlazado; y los procesos `worker-bulk` y `worker-scheduler` ejecutan archivos de código distintos de los backend recién desplegados. No se detectaron referencias huérfanas en las asignaciones ni registros sin formulario existente.

## Método y evidencia

| Comprobación | Resultado |
| --- | --- |
| Sitio HTTPS `/` y API `/api/v1/health/ready` | HTTP 200 y HTTP 200. |
| Acceso anónimo a sesión, listado de formularios, runtime y eliminación | HTTP 401 en rutas protegidas comprobadas. |
| Servicios Docker | `backend-1`, `backend-2`, balanceador, PostgreSQL y Redis en estado saludable; frontend y ambos workers en ejecución. Los workers no tienen chequeo de salud en la salida consultada. |
| Migraciones | Base de datos en `0078_gestor_teams`, última migración disponible. |
| Backend | `python -m pytest -q --tb=short` sobre la imagen desplegada, con directorio temporal de archivos preparado: **486 aprobadas**, 340 avisos, 8 min 4 s. |
| Frontend | `npm test` sobre copia temporal del código del VPS: **105 aprobadas en 22 archivos**. El build de producción terminó correctamente al desplegar. |
| Escritorio | `npm test` sobre copia temporal del código del VPS: **17 aprobadas** (cola local, lotes de sincronización e impresión). |

El primer intento de pruebas del backend, usando las variables de producción dentro del contenedor de prueba, dio 14 fallos por mezcla de configuraciones. El segundo, aislado de esas variables, dio 3 fallos porque la imagen temporal carecía de `/app/uploads`. Esos tres casos pasaron al crear el directorio en el contenedor temporal; la ejecución completa posterior obtuvo 486 aprobadas. Ninguno de esos pasos alteró la instalación activa.

## Cobertura por funcionalidad

| Área | Evidencia automatizada | Validación directa en producción | Estado de validación |
| --- | --- | --- | --- |
| Autenticación, roles y permisos | Pruebas de sesión, contraseñas, permisos, jerarquía y auditoría aprobadas. | Rutas protegidas rechazaron solicitudes anónimas. | Parcial en vivo: no se inició sesión con perfiles reales. |
| Formularios, XLSForm, reemplazo, versiones y Grupos Pull | Pruebas de constructor, importación, duplicación, reemplazo, fuentes y expresiones aprobadas. | API saludable y tablas existentes. | Automatizada; no se importó un archivo desde la UI de producción. |
| Participantes, equipos y asignaciones | Pruebas de participantes, equipos, fuentes y asignaciones aprobadas. | 236 participantes, 1 equipo, 41 asignaciones; integridad referencial comprobada. | Automatizada y datos inspeccionados; asignaciones vigentes pendientes. |
| Captura, registros, revisión y actas | Pruebas de runtime, estados, correcciones, aprobación, actas y archivos aprobadas. | 9 registros existentes; 7 enviados, 1 aprobado y 1 anulado. | Automatizada; no se creó ni editó una respuesta real durante esta validación. |
| Reportes, exportaciones, ERP y mapas | Pruebas de reportes, exportación, ERP y GIS aprobadas. | No se descargaron archivos ni se consultaron informes con sesión. | Automatizada; falta recorrido funcional autenticado. |
| Trabajo sin conexión y escritorio | 17 pruebas de escritorio y pruebas frontend de cola y sincronización aprobadas. | No se conectó un equipo de escritorio real al VPS durante esta validación. | Automatizada; sincronización bidireccional real pendiente de comprobar. |
| Integraciones, mensajería y respaldos | Pruebas de API, mensajería, correo, almacenamiento, copias y scheduler aprobadas. | Servicios activos; no se enviaron correos, mensajes ni copias reales. | Automatizada; integraciones externas pendientes de prueba con cuentas controladas. |

## Hallazgos y prioridad

### 1. Asignaciones sin formulario operativo — alta

La base tiene **10 formularios**: 1 borrador, 1 publicado y 8 eliminados lógicamente. Las **41 asignaciones** existentes corresponden a formularios eliminados; el formulario publicado y el borrador no tienen asignaciones. El borrador está configurado como cerrado con fuente de equipo, por lo que necesitará asignaciones a responsables antes de que estos puedan capturarlo cuando se publique. El formulario publicado usa configuración heredada y puede permitir captura por otro mecanismo; por eso no se concluye que toda captura esté bloqueada. Se recomienda revisar qué formulario debe seguir operativo y reasignar allí participantes y responsables, sin borrar el historial.

### 2. Registros sin participante — media

**5 de 9 registros** no tienen `participant_id`: 4 pertenecen a formularios eliminados y 1 a un formulario publicado. Esto limita el árbol e informes por participante y puede ser válido para registros heredados o formularios abiertos. Se debe revisar la intención de esos cinco casos antes de enlazarlos; no se modificaron automáticamente.

### 3. Versiones distintas en los workers — media

Los archivos del servicio de fuentes de participantes tienen sumas SHA-256 distintas entre `backend-1`, `worker-bulk` y `worker-scheduler`; los workers fueron creados antes del despliegue reciente. Se recomienda reconstruir y reiniciar ambos workers con la revisión actual y después probar una tarea masiva y una programada en un entorno controlado. Estar en estado `running` no confirma que procesen correctamente las funciones nuevas.

### 4. Pruebas de recorrido real aún pendientes — cobertura

No se recibió una sesión de pruebas activa para ejecutar en producción: crear formulario, asignar usuario y participante, capturar sin conexión, sincronizar, editar, aprobar, generar acta, exportar y comprobar permisos entre perfiles. Las pruebas automatizadas cubren reglas individuales, pero no sustituyen ese recorrido completo con navegador y escritorio reales.

## Comprobaciones de integridad adicionales

- 0 registros apuntan a un formulario inexistente.
- 0 asignaciones apuntan a un participante inexistente y 0 a un responsable inexistente.
- 0 grupos de documentos duplicados dentro del mismo proyecto, entre participantes con documento informado.

## Próximo orden de validación

1. Preparar un formulario de prueba vigente con participantes y al menos un responsable asignado; verificar su aparición en web y escritorio.
2. Ejecutar un recorrido completo con cuentas de capturador, aprobador y administrador: captura, corrección, aprobación, acta y exportación.
3. Repetir el recorrido sin conexión y sincronizar al recuperar red, comprobando que no duplique registros.
4. Actualizar los workers y verificar trabajos masivos y programados con evidencia de ejecución.
5. Revisar los cinco registros sin participante y decidir cuáles deben vincularse.

**Conclusión:** las baterías automatizadas y la infraestructura básica pasan; la preparación de asignaciones vigentes, la alineación de workers y el recorrido autenticado de extremo a extremo son las condiciones pendientes para afirmar que todas las funcionalidades operan correctamente en producción.

## Revalidación posterior de los hallazgos

Se repitieron las consultas de solo lectura en el VPS y se obtuvieron los mismos resultados: 1 formulario borrador, 1 publicado, 8 eliminados; las 41 asignaciones pertenecen a formularios eliminados; 5 registros carecen de participante enlazado. Las 41 asignaciones están a nombre de la cuenta de prueba de escritorio indicada por el usuario. La ruta `GET /form-assignments/mine/{project_id}` filtra explícitamente `BuilderTemplate.status == "published"`, por lo que esas 41 asignaciones no pueden aparecer en su escritorio. Este punto queda confirmado como causa concreta de la ausencia de formularios asignados, no solo como sospecha basada en recuentos.

También se verificó que los contenedores `worker-bulk` y `worker-scheduler` no incluyen el módulo `gestor_teams.py`, presente en el backend actual. Esto confirma que ejecutan una versión anterior; no demuestra por sí solo que todas sus tareas fallen. La API de preparación siguió respondiendo HTTP 200 y los backend, balanceador, PostgreSQL y Redis permanecieron saludables.

El usuario pospuso el inicio de sesión en el navegador integrado. Por ese motivo permanecen pendientes las pruebas visuales de captura, revisión, actas, exportación y sincronización con una cuenta autenticada. No se alteraron datos de producción durante esta revalidación.

