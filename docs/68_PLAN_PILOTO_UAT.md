# Plan piloto UAT

## Objetivo

Validar InfoMatt360 con usuarios reales antes de pasar a produccion, usando
procesos de muestra, datos controlados y criterios claros de aceptacion.

UAT significa prueba de aceptacion de usuario. No reemplaza las pruebas
automaticas; confirma que el software sirve para la operacion real.

## Alcance recomendado

Piloto inicial:

- 1 proyecto real o semirreal;
- 2 formularios representativos;
- 3 a 5 usuarios;
- 1 flujo de aprobacion;
- 1 integracion API de prueba o simulada;
- 1 reporte exportado;
- 1 mapa con registros georreferenciados;
- 1 revision de auditoria.

## Roles participantes

| Rol | Responsabilidad |
| --- | --- |
| Administrador | Crear usuarios, permisos, flujos, API keys y revisar auditoria. |
| Capturador | Crear registros desde formularios y adjuntar evidencias. |
| Aprobador | Revisar registros y ejecutar acciones del flujo. |
| Supervisor | Revisar dashboard, reportes, mapas y metricas. |
| Integrador | Probar API key, sincronizacion bulk e idempotencia. |

## Preparacion

1. Ejecutar `.\scripts\preflight.cmd`.
2. Ejecutar `.\scripts\check-full-stack.cmd`.
3. Confirmar credenciales demo o crear usuarios piloto.
4. Definir formularios y campos reales a validar.
5. Preparar datos de prueba sin informacion sensible.
6. Documentar responsables y fecha de ejecucion.

## Escenarios de aceptacion

| ID | Escenario | Resultado esperado |
| --- | --- | --- |
| UAT-01 | Login y seleccion de proyecto | El usuario entra y ve solo su proyecto/permisos. |
| UAT-02 | Crear formulario | El administrador crea o ajusta una plantilla sin tocar codigo. |
| UAT-03 | Capturar registro | El usuario guarda un registro con campos obligatorios y evidencia. |
| UAT-04 | Consultar registros | El registro aparece en busqueda, detalle y dashboard. |
| UAT-05 | Aprobacion | El aprobador ejecuta el paso correcto y queda historial. |
| UAT-06 | Reporte | El supervisor exporta reporte XLSX/CSV y valida datos. |
| UAT-07 | Mapa | Los registros con coordenadas aparecen en mapa. |
| UAT-08 | Usuario admin | El administrador corrige correo o reinicia contrasena con confirmacion. |
| UAT-09 | API key | Se crea API key, se prueba una llamada y se revoca con confirmacion. |
| UAT-10 | Bulk sync | Se procesa lote de prueba y se revisan errores/reintentos. |
| UAT-11 | Auditoria | Las operaciones sensibles aparecen en auditoria. |
| UAT-12 | Metricas | El panel muestra trafico, errores y estado operacional. |

## Evidencia minima

Por cada escenario registrar:

- fecha;
- usuario;
- modulo;
- datos usados;
- resultado: aprobado, observado o rechazado;
- comentario;
- captura o identificador del registro cuando aplique.

Plantilla sugerida:

```text
docs/69_PLANTILLA_EVIDENCIA_UAT.md
```

Guia detallada por modulo:

```text
docs/70_GUIA_EJECUCION_UAT_MODULOS.md
```

Para generar una copia lista para diligenciar con el ultimo ZIP y SHA256:

```powershell
.\scripts\make-uat-evidence.cmd -ProjectName "Piloto InfoMatt360" -Environment "Local"
```

Para confirmar que la evidencia apunta al ultimo ZIP y al SHA256 correcto:

```powershell
.\scripts\check-uat-readiness.cmd
```

Para generar una carpeta lista para compartir con el equipo UAT:

```powershell
.\scripts\make-uat-kit.cmd -ProjectName "Piloto InfoMatt360" -Environment "Local"
```

El resultado incluye resumen UAT, carpeta editable y un ZIP del kit para
compartir.

Para resumir automaticamente los resultados registrados en la evidencia UAT:

```powershell
.\scripts\summarize-uat-evidence.cmd
```

Antes de sentar usuarios a validar, se puede ejecutar la pre-UAT tecnica:

```powershell
.\scripts\run-uat-technical-checks.cmd
```

## Criterios de salida

El piloto se considera aprobado cuando:

- 100% de escenarios criticos pasan: login, captura, registros, permisos,
  aprobacion, auditoria y reportes;
- no hay errores bloqueantes;
- las observaciones menores tienen responsable;
- el administrador entiende el runbook funcional;
- el equipo acepta que el sistema puede pasar a ambiente de staging o piloto
  ampliado.

## Clasificacion de hallazgos

| Severidad | Descripcion | Accion |
| --- | --- | --- |
| Bloqueante | Impide login, captura, permisos, aprobacion o consulta principal. | Corregir antes de seguir. |
| Alta | Permite operar, pero con riesgo de datos, seguridad o trazabilidad. | Corregir antes de produccion. |
| Media | Afecta experiencia o eficiencia, sin riesgo critico. | Planificar correccion. |
| Baja | Texto, estilo o mejora menor. | Registrar en backlog. |

## Acta de cierre sugerida

La plantilla completa esta en `docs/69_PLANTILLA_EVIDENCIA_UAT.md`.

```text
Proyecto:
Fecha:
Responsable:
Version/ZIP:
SHA256:

Escenarios ejecutados:
Escenarios aprobados:
Hallazgos bloqueantes:
Hallazgos abiertos:

Decision:
[ ] Aprobado para staging
[ ] Aprobado con observaciones
[ ] No aprobado

Firmas:
```

## Siguiente paso despues del UAT

Si el piloto se aprueba:

1. congelar version;
2. generar ZIP y SHA256;
3. preparar `.env.production`;
4. ejecutar `doctor-production`;
5. preparar backup;
6. desplegar en staging o produccion controlada;
7. monitorear con `docs/65_OPERACION_MONITOREO_INCIDENTES.md`.
