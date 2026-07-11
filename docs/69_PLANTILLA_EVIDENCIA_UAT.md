# Plantilla de evidencia UAT

## Datos generales

| Campo | Valor |
| --- | --- |
| Proyecto |  |
| Ambiente | Local / Staging / Produccion controlada |
| Version ZIP |  |
| SHA256 |  |
| Fecha inicio |  |
| Fecha cierre |  |
| Responsable UAT |  |
| Participantes |  |

## Registro de escenarios

| ID | Escenario | Usuario/Rol | Fecha | Resultado | Evidencia | Hallazgo asociado | Comentario |
| --- | --- | --- | --- | --- | --- | --- | --- |
| UAT-01 | Login y seleccion de proyecto |  |  | Pendiente |  |  |  |
| UAT-02 | Crear formulario |  |  | Pendiente |  |  |  |
| UAT-03 | Capturar registro |  |  | Pendiente |  |  |  |
| UAT-04 | Consultar registros |  |  | Pendiente |  |  |  |
| UAT-05 | Aprobacion |  |  | Pendiente |  |  |  |
| UAT-06 | Reporte |  |  | Pendiente |  |  |  |
| UAT-07 | Mapa |  |  | Pendiente |  |  |  |
| UAT-08 | Usuario admin |  |  | Pendiente |  |  |  |
| UAT-09 | API key |  |  | Pendiente |  |  |  |
| UAT-10 | Bulk sync |  |  | Pendiente |  |  |  |
| UAT-11 | Auditoria |  |  | Pendiente |  |  |  |
| UAT-12 | Metricas |  |  | Pendiente |  |  |  |

Valores sugeridos para Resultado:

- Aprobado;
- Observado;
- Rechazado;
- Pendiente.

## Registro de hallazgos

| ID | Fecha | Modulo | Severidad | Descripcion | Pasos para reproducir | Responsable | Estado | Decision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| H-001 |  |  |  |  |  |  | Abierto |  |

Valores sugeridos para Severidad:

- Bloqueante;
- Alta;
- Media;
- Baja.

Valores sugeridos para Estado:

- Abierto;
- En revision;
- Corregido;
- Aceptado como observacion;
- Cerrado.

## Acta de cierre

Antes de completar el acta se puede generar un resumen automatico:

```powershell
.\scripts\summarize-uat-evidence.cmd
```

```text
Proyecto:
Ambiente:
Version/ZIP:
SHA256:
Fecha:

Escenarios ejecutados:
Escenarios aprobados:
Escenarios observados:
Escenarios rechazados:

Hallazgos bloqueantes abiertos:
Hallazgos altos abiertos:
Hallazgos medios/bajos abiertos:

Decision:
[ ] Aprobado para staging
[ ] Aprobado para piloto ampliado
[ ] Aprobado con observaciones
[ ] No aprobado

Observaciones:

Responsable funcional:
Responsable tecnico:
Firma/aprobacion:
```

## Reglas de uso

- No registrar datos personales reales si no son necesarios para la prueba.
- Usar identificadores de registro en vez de capturas con informacion sensible.
- Adjuntar evidencia de errores con fecha, usuario, modulo y `X-Request-ID` si existe.
- Todo hallazgo bloqueante debe corregirse antes de produccion.
- Todo hallazgo aceptado como observacion debe quedar documentado con responsable.
