# Flujos de carga autenticada

`k6-functional-flows.js` prueba cuatro rutas reales de InfoMatt360: búsqueda paginada de respuestas, captura individual, sincronización de respuestas por lotes y exportación CSV. Puede incluir el XLSX de resumen con `ENABLE_XLSX=true` si la cuenta tiene acceso territorial irrestricto.

## Preparación

1. Crea o elige un **proyecto exclusivo de pruebas** y una plantilla publicada con campos conocidos. Asigna a la cuenta de carga permisos de lectura y `records.write`.
2. Asigna participantes distintos a esa cuenta en el formulario. Separa los IDs de captura y de sincronización en dos archivos de texto, uno por línea. Cada participante se utiliza **una sola vez**. No reutilices archivos ni `RUN_ID` en otra ejecución.
3. Define `VALUES_JSON` con valores válidos para esa plantilla, por ejemplo `{"nombre":"Prueba de carga","integrantes":2}`. El script marca cada registro en `device_id` como `loadtest-<RUN_ID>-...` para identificarlo al comprobar y limpiar el proyecto.
4. Entrega `ACCESS_TOKEN` o `LOGIN_EMAIL` y `LOGIN_PASSWORD` mediante variables de entorno de un gestor de secretos. El script no contiene credenciales y hace un solo inicio de sesión por ejecución. Evita imprimir las variables en terminal o guardarlas en el repositorio.

## Perfiles

| `PROFILE` | Comportamiento | Datos creados |
|---|---|---|
| `read` | Rampa de búsquedas paginadas | Ninguno |
| `capture` | Una respuesta por participante de `CAPTURE_IDS_FILE` | Sí |
| `sync` | Lotes de 1–20 participantes de `SYNC_IDS_FILE` | Sí |
| `export` | CSV, con XLSX opcional y limitado a una solicitud por cada seis iteraciones | Ninguno |
| `all` | Los cuatro perfiles simultáneos | Sí |

`PROFILE=read` es el valor predeterminado. Los perfiles con escritura exigen `ENABLE_WRITES=true`, `TEST_PROJECT_CONFIRMED=yes`, `RUN_ID` único, `VALUES_JSON` y archivos de participantes. El script falla antes de enviar solicitudes si faltan estas condiciones. `CAPTURE_PARTICIPANT_IDS` y `SYNC_PARTICIPANT_IDS` aceptan listas separadas por coma para pruebas pequeñas.

Ejemplo de ejecución con variables preparadas en el entorno:

```sh
k6 run -e PROFILE=all -e BASE_URL=https://infomatt360.tecnomatt.com \
  -e PROJECT_ID=ID_DEL_PROYECTO_DE_PRUEBAS -e TEMPLATE_ID=ID_DEL_FORMULARIO_DE_PRUEBAS \
  -e ENABLE_WRITES=true -e TEST_PROJECT_CONFIRMED=yes -e RUN_ID=prueba20261006a \
  -e CAPTURE_IDS_FILE=./capture_ids.txt -e SYNC_IDS_FILE=./sync_ids.txt \
  -e SYNC_BATCH_SIZE=5 -e READ_VUS=2 -e WRITE_VUS=2 -e EXPORT_VUS=1 \
  loadtest/k6-functional-flows.js
```

También deben estar definidas `ACCESS_TOKEN` o las variables de inicio de sesión y `VALUES_JSON`. k6 recibe variables externas con `-e NOMBRE=valor`; pasa las credenciales desde tu mecanismo seguro sin escribirlas en el comando. Si usas un contenedor, monta el script y los archivos de participantes dentro de él.

## Validación y límites

El preflight confirma que la cuenta puede abrir la plantilla y buscar registros. Captura comprueba el ID y el participante devueltos. Sincronización comprueba `received`, `created`, `failed` y cada elemento del lote. `VERIFY_REPLAY=true` reenvía el mismo lote y exige `replayed=true` con el mismo `job_id`, para verificar idempotencia. El script registra `flow_failures` y `loadtest_records_created` además de métricas HTTP y latencia por ruta.

Para varias máquinas independientes, usa listas **disjuntas** de participantes y un `RUN_ID` diferente por máquina. `SHARD_OFFSET` permite diferenciar marcadores de una partición del mismo ensayo. En una ejecución distribuida nativa de k6, `iterationInTest` ya es único dentro de cada escenario.

Empieza con 1–2 usuarios virtuales y pocos participantes, comprueba los registros creados, luego aumenta la carga por etapas mientras observas API, PgBouncer, PostgreSQL y Redis. Detén la prueba ante errores sostenidos >1 %, p95 >2 s, una réplica no saludable o conexiones de PostgreSQL próximas al máximo. Los umbrales de k6 fallan al finalizar una corrida; el operador debe vigilar y detener una degradación durante la ejecución. El límite de tasa por IP sigue activo y puede producir `429` antes de saturar la aplicación.

La ejecución final debe comparar los IDs y participantes esperados con los registrados, confirmar que ningún reintento creó duplicados y limpiar los datos marcados. Este script **no borra registros automáticamente**. Las pruebas previas de lectura pública están en [docs/131](../docs/131_PRUEBA_ESTRES_VPS_2026-10-06.md) y [docs/132](../docs/132_PRUEBA_DISTRIBUIDA_VPS_2026-10-06.md).
