# 141. Funcionalidades incorporadas a la hoja de ruta

**Captura híbrida, paginación configurable, validación, devoluciones, reasignación, sincronización y exportaciones independientes**

Documento de alcance funcional y técnico · Octubre de 2026.

> **Documento oficial.** Es la versión prioritaria, tomada de
> `INFO_MATT_360_Funcionalidades_Adicionadas_y_Plan_de_Implementacion.docx`.
> Reemplaza a `140_DEVOLUCIONES_MASIVAS_SINCRONIZACION_Y_EXPORTACIONES_LIMPIAS.md`
> y a `141_ALCANCE_DETALLADO_ULTIMAS_FUNCIONALIDADES.md`, que se retiraron por
> duplicados; siguen en el historial de git. El estado de implementación de
> cada sección está en [docs/142](142_VALIDACION_FUNCIONALIDADES_DOCS141.md).
> Las referencias "docs/141 §N" del código apuntan a las secciones de este
> documento.

## 1. Propósito y alcance

Este documento precisa:
- las últimas funcionalidades acordadas para INFO-MATT 360;
- el comportamiento esperado;
- los roles;
- la información que debe conservarse;
- la forma propuesta de implementarlas sobre los módulos existentes.

No debe interpretarse como certificación de que las funciones ya operan en producción.

## 2. Paginación diseñada por el constructor

El diseñador define manualmente páginas y secciones: título, orden, grupos de
preguntas y reglas de visibilidad. No se dividirán automáticamente las
preguntas por una cantidad fija. Las secciones relacionadas permanecen juntas,
aunque el formulario tenga 300 o más preguntas.

Un grupo REPEAT (por ejemplo, integrantes del núcleo familiar) se mantiene
dentro de su sección, y cada integrante conserva sus respuestas. Las matrices,
adjuntos, reglas condicionales y referencias entre páginas siguen funcionando.
El avance y el borrador deben recuperarse en la página correcta.

## 3. Participante como eje de consulta multidispositivo

Un gestor autorizado podrá consultar, aun sin Internet después de la descarga
inicial:
- la ficha del participante;
- los formularios asignados y sus estados;
- las respuestas previas;
- las evidencias permitidas.

Los formularios ya aplicados se muestran en lectura; la aplicación no debe
crear un segundo registro ordinario de la misma actividad.

El acceso es por proyecto, territorio, asignación y rol. El servidor es la
fuente oficial. La copia local se limita a datos autorizados y debe contemplar
protección y revocación de acceso.

## 4. Estados de edición y responsabilidades

| Estado | Gestor destinatario | Coordinador / administrador |
|---|---|---|
| Borrador | Editar y guardar sin enviar | Consultar según ámbito y permisos |
| Enviado / en revisión | Solo lectura | Revisar, observar, devolver o aprobar según rol |
| Devuelto | Editar el mismo registro y reenviar | Asignar responsable y verificar corrección |
| Reenviado | Solo lectura | Revisar, aprobar o devolver de nuevo |
| Aprobado | Solo lectura | Sin edición ordinaria; excepción administrativa separada |

Se elimina la idea de "dos ediciones libres" después del envío. La edición
posterior requiere una devolución formal. El autor original del registro no
cambia aunque la corrección se reasigne a otro gestor.

## 5. Devoluciones individuales y masivas

El revisor puede devolver al capturista original o asignar la corrección a
otro gestor específico.

Para lotes se importará un Excel con estas columnas:
- ID de registro;
- acción (devolver al original o reasignar);
- usuario de destino;
- observación;
- campo afectado;
- motivo.

Antes de aplicar cambios se validarán el estado, la existencia, los
duplicados, los permisos, el proyecto y el ámbito territorial.

La carga masiva tendrá vista previa, confirmación, procesamiento por lotes,
idempotencia, resultados por fila y archivo de errores. Un registro podrá tener
varias observaciones sin duplicarse en la base de respuestas.

## 6. Retroalimentación dentro del registro

El revisor dispondrá de un panel independiente de "Validación y
retroalimentación". Cada observación tendrá:
- resultado;
- motivo general;
- pregunta afectada, o campo específico de un REPEAT;
- evidencia asociada;
- acción solicitada.

Los estados de una observación son pendiente, en corrección, corregida,
verificada o rechazada.

El gestor destinatario verá las observaciones al abrir la devolución y podrá
navegar a la página, pregunta e integrante exactos. Las observaciones no
alteran automáticamente las respuestas; se conserva el historial de revisiones
y correcciones.

## 7. Sincronización diferencial y corrección en otra tablet

Antes de transferir una devolución, el sistema compara:
- el ID del registro;
- la versión de respuestas;
- la versión de plantilla;
- el estado;
- el manifiesto de adjuntos.

Si el dispositivo ya tiene el contenido completo, recibe solo el cambio de
estado, permisos y observaciones. Si el destinatario es otro gestor sin copia
local, recibe el formulario con todas las respuestas, matrices, REPEAT y
archivos autorizados.

Una tablet desconectada no puede conocer en tiempo real una aprobación o
reasignación efectuada en otro equipo. Por eso, al sincronizar se vuelven a
validar permisos, estado y versión. Los conflictos se conservan para revisión
y nunca sobrescriben silenciosamente la versión oficial.

## 8. Dos exportaciones independientes

| Salida | Incluye | Excluye |
|---|---|---|
| Respuestas limpias | ID, datos técnicos necesarios, preguntas y respuestas; filtros por estado, periodo y territorio | Observaciones, devoluciones, comentarios y auditoría |
| Observaciones / calidad | ID del registro, pregunta, ruta REPEAT, motivo, acción, revisor, fechas y estado | Columnas de respuestas como estructura analítica principal |
| Auditoría (opcional) | Versiones, responsables, cambios y eventos de revisión | No es la exportación estándar para informes |

Las observaciones se relacionan con las respuestas mediante el ID de registro,
pero se almacenan por separado. Varias observaciones sobre un registro no deben
multiplicar sus filas en la exportación de respuestas. Para reportes oficiales
se propone seleccionar registros aprobados por defecto, dejando los demás
filtros explícitos.

## 9. Arquitectura propuesta: reutilizar, no duplicar

Se reutilizarán los módulos de Runtime, registros, participantes,
asignaciones, revisión, permisos y colas offline (IndexedDB/SQLite).

Se proponen entidades independientes para:
- observaciones;
- destinatarios de corrección;
- importaciones masivas;
- manifiestos de sincronización.

Las nuevas APIs deberán aplicar permisos por registro, y no únicamente el
permiso general `records.write`.

## 10. Ejemplo operativo integral

1. Juan captura y envía la Visita 3 del participante A; el registro queda bloqueado.
2. El coordinador detecta fecha y firma incorrectas, registra dos observaciones y devuelve el registro a María mediante Excel.
3. María sincroniza su tablet. Como no tiene ese registro, recibe respuestas, integrantes REPEAT, evidencias y observaciones.
4. María corrige fuera de línea y reenvía al recuperar la conexión. El servidor valida autorización y versión.
5. El coordinador verifica y aprueba. La base de respuestas exporta los datos corregidos sin observaciones; la base de calidad conserva los dos hallazgos y su trazabilidad.

## 11. Pruebas obligatorias y criterios de aceptación

- Formulario de 350+ preguntas con páginas configurables, REPEAT, matrices, condicionales y adjuntos.
- Bloqueo efectivo: borrador editable, enviado bloqueado, devuelto editable solo por el destinatario, aprobado bloqueado.
- Devolución masiva de 1.000 filas con errores parciales, reintentos sin duplicación y trazabilidad.
- Reasignación a otra tablet: transferencia completa de respuestas y evidencias, sin cambiar el autor original.
- Devolución al dispositivo original: sincronización diferencial sin descargar archivos ya disponibles.
- Conflictos offline: impedir la sobrescritura y preservar los cambios pendientes.
- Exportación limpia: ninguna observación ni duplicación de registros; exportación separada de hallazgos.

## 12. Estado de ejecución y próximos pasos

Al redactar el documento:
- **Verificado en el repositorio:** ya existían servicios de corrección,
  revisión, reapertura, asignaciones, control de versiones y componentes de
  cola offline.
- **Pendiente de implementar y probar integralmente:**
  - observaciones estructuradas por pregunta;
  - devolución y reasignación masivas;
  - autorización individual de corrección;
  - sincronización bidireccional diferencial con adjuntos;
  - exportaciones separadas certificadas.

**Avance posterior:** está en [docs/142](142_VALIDACION_FUNCIONALIDADES_DOCS141.md).

Orden propuesto:
1. modelo y migraciones;
2. permisos y flujo de devolución;
3. observaciones y exportaciones;
4. importación masiva;
5. sincronización móvil y de escritorio;
6. pruebas automatizadas y UAT;
7. despliegue controlado.

## 13. Referencias técnicas

- **Repositorio:** amopanta/infomatt360. **Rama:** `feature/hybrid-offline-capture-20261017`.
- **Referencias existentes:**
  - `backend/app/api/v1/review.py`
  - `backend/app/api/v1/runtime.py`
  - `backend/tests/test_form_assignments_reopening.py`
  - `backend/tests/test_runtime_record_correction.py`
  - `docs/125_FLUJO_FORMULARIOS_PARTICIPANTES_Y_CAPTURA.md`
