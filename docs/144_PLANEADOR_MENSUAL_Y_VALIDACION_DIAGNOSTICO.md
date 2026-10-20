# 144. Planeador mensual y validación del diagnóstico integral

Fecha: 2026-10-19. Rama: `feature/hybrid-offline-capture-20261017`.
Fuente: `Diagnostico_InfoMatt360.docx` («Diagnóstico integral funcional y plan
de ajustes», 19 de octubre de 2026).

## 1. Validación del diagnóstico contra el código

El diagnóstico se basa en una revisión anterior y cita los documentos
retirados `140_DEVOLUCIONES…` y `141_ALCANCE…`. Lo que daba como «cambio en
rama» o «por verificar» ya está construido y probado (docs/141 y 142).

| Tema del diagnóstico | Estado | Dónde |
|---|---|---|
| Devolución individual y masiva, mismo registro, autor sin cambios, solo corrige el destinatario | Ya existía | docs/141 §4–§5, `correction_service.ensure_can_edit` |
| Observaciones por pregunta e instancia REPEAT, separadas de las respuestas | Ya existía | `review_observations` |
| Exportación limpia y exportación de observaciones | Ya existía | `clean-export.csv`, `observations.csv` |
| Aprobado bloqueado; reapertura con motivo obligatorio | Ya existía | `reopen_approved` |
| Edición concurrente sin sobrescritura | Ya existía | `lock_version` → 409 |
| Descarga inicial, cola, reintentos sin duplicar, conflictos (OFF-01 a OFF-06) | Ya existía | tablet (docs/142) y escritorio (docs/130) |
| Pérdida del equipo (OFF-08) | Ya existía | base por usuario, borrado remoto |
| Baja de un usuario revoca el acceso y conserva el historial | Ya existía | `get_current_user` rechaza `status != active` |
| Control territorial en el servidor y por ID directo (SEC-01) | Ya existía | barridos H11 (docs/140 §10) |
| Asignación masiva con vista previa y resultado por fila | Ya existía | `POST /form-assignments/templates/{id}/bulk-assign` |
| Reporte de compatibilidad al importar XLSForm | Ya existía | avisos de `xlsform_import_service` |
| ERP: reabrir un aprobado sin doble movimiento | Ya existía | `erp_service.reverse_settlement` |
| Estado por formulario en la vista del participante (devuelto, aprobado) | **Ajustado** | `/form-assignments/mine` devuelve `record_status` |
| Cambio de responsable con motivo y fecha efectiva | **Ajustado** | `AssignmentWrite.reason`; auditoría `reassign_form` con el responsable anterior |
| Reemplazo de un soporte conserva el anterior | Ya existía | la auditoría de `correct_field` guarda el valor anterior y el archivo no se borra |
| Zona horaria y fecha de actividad frente a sincronización | **Nuevo** | configuración del planeador |
| Planeador mensual, población, metas, cortes y Excel de tres hojas | **Nuevo** | este documento |
| Coordinador del equipo | **Nuevo** | `gestor_teams.coordinator_user_id`, configurable |

## 2. Planeador mensual

Pantalla **Revisión y reportes → Planeador mensual** (`/planner`). Pestañas:
Tablero, Metas, Programación, Población objetivo y Configuración.

### Reglas configurables por proyecto (`planner_settings`)

| Regla | Opciones | Por defecto |
|---|---|---|
| Qué cuenta como ejecutado | `approved`: solo lo aprobado · `submitted`: todo lo que llega (enviado, en revisión, devuelto, corregido o aprobado) | aprobado |
| Llave de familia | el participante · su documento · su código · un campo del formulario | el participante |
| Fecha de la actividad | un campo del formulario; vacío = fecha de registro | fecha de registro |
| Municipio en formularios sin participante | un campo del formulario; si no, el territorio único del gestor | — |
| Zona horaria | p. ej. `America/Bogota` | `America/Bogota` |

Nunca cuentan los borradores, anulados, cancelados, rechazados ni los
registros hijos de un REPEAT. La **actividad es el formulario**: abiertos y
cerrados, con o sin participante.

### Cálculo

- Cumplimiento = ejecutado válido ÷ meta × 100 si la meta es mayor que cero.
  Con meta cero se muestra «Sin meta». Por encima de 100 % se muestra el valor
  real; solo la barra se limita.
- Los totales se ponderan: suma de ejecutados ÷ suma de metas, nunca el
  promedio de porcentajes. Ejemplo verificado: 85/100 y 80/80 → 91,67 %.
- Lo ejecutado sin meta se informa aparte como **«Ejecutado sin meta (a
  revisar)»** y no infla el cumplimiento.
- Familias únicas y visitas se cuentan por separado: una familia con dos
  visitas suma dos actividades y una familia.
- Cobertura = familias únicas ÷ familias objetivo del municipio.
- Meta municipal: si hay una meta sin gestor, esa manda; si no, se suman las
  metas de los gestores. Así no se cuenta dos veces.

### Metas, población y programación

- Metas por año, mes, municipio, actividad, gestor opcional y unidad
  (actividades o familias únicas). Cada combinación tiene una sola meta.
- Cambiar una meta o la población exige justificación. El historial
  (`planner_history`) guarda el valor anterior y el nuevo, quién, cuándo, el
  motivo y el origen, y solo admite inserciones.
- **Importación** CSV/XLSX: plantilla → validar → vista previa con el impacto
  en el total → confirmar → archivo de errores. Columnas: `anio, mes,
  municipio, formulario, gestor (correo), unidad, meta, modo
  (crear|reemplazar|sumar), justificacion`.
  - Se valida: período, mes cerrado, municipio dentro del territorio de quien
    importa, formulario, gestor activo del proyecto, entero ≥ 0, duplicados
    en el archivo y justificación para reemplazar o sumar.
  - Con errores no se aplica nada. Repetir la misma carga no duplica ni vuelve
    a sumar: cada fila aplicada queda marcada por el hash del archivo.
- **Programación del gestor:** actividad, fechas, cantidad y participantes
  previstos. El municipio y el coordinador se heredan de su asignación
  vigente. Reprogramar o cancelar exige justificación y queda en el
  historial. Lo programado aparece en el detalle aunque aún no tenga meta.

### Cortes

**Cerrar corte del mes** congela la ejecución y las metas de ese mes con las
reglas vigentes (`planner_cuts`). Después, ni un registro nuevo ni un
cambio de meta alteran ese mes; sus metas ya no se pueden editar.

### Excel consolidado (un solo .xlsx)

| Hoja | Contenido |
|---|---|
| Resumen municipal | mes, municipio, actividad, población objetivo, meta, ejecutado válido, pendiente, % y familias únicas |
| Detalle por gestor | coordinador, gestor, municipio, actividad, fechas, programado, participantes previstos, meta, ejecutado, %, estado |
| Consolidado general | totales por mes, municipio, coordinador y actividad; acumulado del año; actividades y familias por separado; fuera de programación y cobertura |

El Excel sale del mismo cálculo que el tablero, con los mismos filtros, corte
y permisos.

### Permisos

| Perfil | Ve | Gestiona |
|---|---|---|
| `planner.manage` o `identity.users.manage` | su territorio | reglas, metas, importación, población, cortes y programación de cualquier gestor |
| Revisor / aprobador / coordinador / `reports.export` | su territorio | — |
| Gestor (`records.write`) | solo lo suyo | su propia programación |
| Sin acceso al proyecto | — (403) | — |

## 3. Migración

`0084_planner`, después de `0083_review_observations`:
- crea `planner_settings`, `planner_population`, `planner_targets`,
  `planner_plans`, `planner_history` y `planner_cuts`;
- agrega `gestor_teams.coordinator_user_id`.

No modifica tablas existentes. Se probó subir, bajar y volver a subir sobre una
copia de la base demo.

## 4. Pruebas

`backend/tests/test_planner.py`, 12 pruebas sobre los criterios del
diagnóstico §7 y §17:
- 85/100 → 85 %, 100/100 → 100 %, meta cero → «Sin meta» y total ponderado
  91,67 %;
- regla de conteo configurable;
- familias únicas frente a visitas, y llave de familia por campo;
- fecha de actividad por campo, y cobertura de población;
- importación: vista previa, aplicar, repetir sin duplicar, `sumar` repetido
  sin doble suma, y validaciones (columnas, mes, formulario, gestor, negativo,
  duplicada, justificación, territorio no autorizado);
- corte cerrado inalterable (META-02);
- vistas por gestor, coordinador y usuario sin acceso;
- Excel de tres hojas que cuadra con el tablero (REP-01);
- programación con herencia y reprogramación justificada;
- coordinador de equipo.

Los barridos de seguridad H11 recorren también las rutas nuevas.

Otras pruebas:
- Suite completa del backend: 541 pruebas.
- Web: 125 pruebas.
- Prueba en el navegador con la base demo:
  - regla «todo lo que llega»;
  - meta de 4 en «h04», con 3 ejecutadas → 75 %;
  - 15 ejecutadas sin meta, informadas aparte;
  - Excel descargado.

## 5. Límites

- El planeador lee los registros en cada consulta. Para volúmenes muy
  grandes conviene un cálculo programado; por ahora un corte cerrado no
  recalcula.
- La fecha de actividad depende de que el formulario tenga ese campo. Sin él
  se usa la fecha en que el registro llegó al servidor, que en capturas sin
  conexión puede ser posterior.
- Los gestores proponen ajustes de su programación, no de las metas
  globales.
