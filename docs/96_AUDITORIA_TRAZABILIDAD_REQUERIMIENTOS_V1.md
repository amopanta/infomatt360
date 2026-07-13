# 96. Auditoría de trazabilidad contra el Documento Maestro de Requerimientos v1.0

## Qué es esto

Re-lectura completa de los 3 documentos fuente oficiales (`InfoMatt_Core_Documentacion_Maestra_Definitiva.pdf`, `InfoMatt_Core_Arquitectura_Maestra.pdf`, `InfoMatt360_Documento_Maestro_Requerimientos_Especificaciones_v1.docx`) contra el estado real del código, para identificar qué queda pendiente de las Fases 0-4 ya cerradas y de los módulos agregados después (ERP, WAHA, DonorSync, ExtAPI, AI Audit, S3, Gobernanza, Asset Lock, Enlace Mágico, formularios públicos, importador multiformato, reemplazo de plantilla).

Los dos PDFs son narrativa de arquitectura de alto nivel (infraestructura Docker, los "7 súper-módulos" ya asimilados, roadmap por fases) y no aportan requisitos nuevos no cubiertos antes. El `.docx` (27 secciones) es mucho más granular y es la fuente de los 14 hallazgos de abajo.

## Hallazgos (verificados leyendo el código, no asumidos)

| # | Requisito (doc §) | Veredicto | Evidencia |
|---|---|---|---|
| 1 | **Base Espejo** — replicación hacia BD externa (Postgres/MySQL/SQL Server/SQLite/ODBC), con prueba de conexión, creación de estructura equivalente y sincronización programada/por eventos en modos insert-only/incremental/espejo completo/respaldo analítico (§17) | **PARCIAL** | `app/models/mirror.py` (`MirrorTarget`, `MirrorPlan`) y `app/services/mirror_service.py` existen pero son solo CRUD (`create_target`, `create_plan`, etc.). No hay conexión real a motores externos, ni prueba de conexión, ni creación de esquema, ni job de sincronización — es un modelo de datos sin motor. Distinto del DonorSync existente (que empuja registros aprobados a una API REST tipo ActivityInfo, no replica una base de datos completa). |
| 2 | Carga masiva por Excel de **asignaciones** (usuarios↔proyectos↔formularios↔territorios↔dispositivos↔permisos) (§10) | **FALTA** | `excel_import_service.py` solo soporta `participants` y `users`. `assignment_service.py` solo tiene alta individual, sin importador. |
| 3 | Carga masiva de **registros históricos/externos** de respuestas por Excel, pasando por el mismo peaje de validación (§10) | **PARCIAL** | Existe `save_records_bulk` (sincronización JSON vía API-key, para dispositivos/lotes), pero no un importador desde archivo Excel para datos históricos externos. |
| 4 | **Constructor visual** de actas/documentos (arrastrar logos, encabezados, tablas, firmas) (§7, §16) | **FALTA** | `ActaTemplateCreate.html_template` es un campo de texto Jinja2 crudo; no existe UI de diseño visual en el frontend. |
| 5 | Generación **masiva** de actas PDF (no solo una por una) (§15, §16) | **FALTA** | `render_acta_pdf` solo acepta un registro por solicitud. |
| 6 | Constructor visual de **reportes/tableros simples** (§7) | **FALTA** | `report_service.py` solo expone un resumen fijo (`project_summary`); el dashboard del frontend son tarjetas fijas, no un constructor. |
| 7 | Descarga masiva de evidencias en **ZIP** filtrada por participante/formulario/proyecto/fecha/estado/gestor, con renombrado automático (§18) | **FALTA** | `file_service.py` solo maneja archivos individuales; no hay endpoint de exportación ZIP masiva. |
| 8 | **GIS real**: columnas de geometría PostGIS, GeoJSON, WMS/WFS (§19) | **PARCIAL** | `GisFeature` guarda lat/lng como `String` y `geometry_json` como texto validado (no una columna de geometría real). Sin PostGIS/GeoAlchemy2, sin WMS/WFS. |
| 9 | Conectores formales para Power BI / Looker / Tableau / Metabase / Superset (§19) | **FALTA** | Solo existe una API de lectura genérica (`external_api.py`), sin conectores nombrados a esas herramientas. |
| 10 | Selección de impresora e impresión masiva/individual desde el **cliente de escritorio** (§15) | **FALTA** | El shell de Electron (`desktop/src/*.js`) solo sirve el frontend estático y maneja la cola offline; no hay integración de impresión nativa. |
| 11 | **Doble bandeja de correo** (bandeja interna + bandeja externa vía IMAP) (§12) | **FALTA** | `mail_autoconfig_service.py` solo envía (SMTP). El único "inbox" del código es una mensajería interna usuario-a-usuario (`message_service.list_inbox`), no una bandeja de correo externo leída por IMAP. |
| 12 | Jerarquía de roles: **Administrador nacional** (sobre todas las organizaciones) vs. **Administrador de proyecto** vs. **Auditor/Consulta** de solo lectura (§21) | **FALTA** | `Role` es un catálogo plano de permisos sin nivel de alcance (organización vs. proyecto); `UserProjectAssignment` ata un rol a un único proyecto. No hay rol nacional ni rol de solo-lectura predefinidos — habría que ensamblarlos manualmente combinando permisos por proyecto. |
| 13 | Vista unificada del **historial del participante** a través de todos los canales (§9) | **FALTA** | `RuntimeRecord` (el motor de captura real) **no tiene `participant_id`**. Solo el modelo `Record` (aparentemente legado/ERP) tiene `participant_id` + `source_channel`. No existe pantalla de historial por participante en el frontend. |
| 14 | Máquina de estados completa: borrador, enviado, en revisión, devuelto, corregido, aprobado, rechazado, **anulado**, **sincronizado** (§13) | **PARCIAL** | Existen 7 de los 9 estados (`draft, submitted, under_review, returned, corrected, approved, rejected` + variantes `tech_approved`/`coordinator_approved`/`cancelled`/`archived`). Faltan explícitamente **anulado** (lo más cercano es `cancelled`/`archived`, no equivalente) y **sincronizado** (no existe como estado de `RuntimeRecord`). |

## Lo que NO es una brecha (ya resuelto, confirmado en auditorías previas)

Backups automáticos, edición concurrente (enlace mágico + asset lock), captura pública por token, instalador multi-paso completo, ERP headless, WhatsApp/WAHA, auditoría semántica IA, storage S3/MinIO/Google Drive, mesa de ayuda, multi-tenancy lógico (Organization), branding dinámico, PWA offline, escritorio Electron básico, XLSForm import/export + plantilla maestra, importador multiformato (SurveyMonkey/LimeSurvey), reemplazo de plantilla en el mismo lugar — ver [[reference-published-artifacts]] y docs/59-95.

## Decisión arquitectónica ya tomada, no una brecha

El aislamiento fuerte "base independiente por proyecto o schema-per-project" (§2) fue evaluado explícitamente al inicio de este ciclo de trabajo y el usuario decidió el modelo de **tenant lógico** (`Organization` sobre `Project`, aislamiento a nivel de aplicación) en vez de aislamiento físico — ver el plan `declarative-spinning-simon.md`. No se re-abre esta decisión salvo que el usuario lo pida explícitamente.

## Priorización sugerida (no decidida aún, pendiente de que el usuario elija)

De más a menos crítico si el objetivo es acercarse al "eje central del participante" y al "peaje de calidad" que describe el documento maestro:

1. **#13 (participante como eje central)** — hoy es la brecha más estructural: el motor de captura real ni siquiera enlaza `RuntimeRecord` a un participante.
2. **#14 (estados anulado/sincronizado)** — cambio pequeño y de bajo riesgo.
3. **#12 (jerarquía de roles nacional/proyecto/auditor)** — afecta gobernanza pero es aditivo, no rompe nada existente.
4. **#1 (Base Espejo real)** — el más grande y más caro de construir bien (soporta múltiples motores externos).
5. El resto (#2, #3, #4, #5, #6, #7, #8, #9, #10, #11) son módulos aditivos independientes entre sí, priorizables según lo que el usuario necesite primero.
