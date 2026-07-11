# Guia de ejecucion UAT por modulos

## Objetivo

Convertir el piloto UAT en una revision guiada por modulos. Esta guia indica
que validar, que evidencia registrar y cuando considerar aprobado cada flujo.

Usar junto con:

- `docs/68_PLAN_PILOTO_UAT.md`
- `docs/69_PLANTILLA_EVIDENCIA_UAT.md`

## Antes de empezar

1. Generar entrega validada:

   ```powershell
   .\scripts\make-delivery.cmd -ProjectName "Piloto InfoMatt360" -Environment "Local"
   ```

2. Ejecutar pre-UAT tecnica:

   ```powershell
   .\scripts\run-uat-technical-checks.cmd
   ```

3. Abrir la evidencia UAT generada en `..\outputs`.
4. Confirmar usuarios y roles:

   | Rol | Usuario sugerido | Modulos |
   | --- | --- | --- |
   | Administrador | Admin piloto | Usuarios, permisos, flujos, API keys, auditoria |
   | Capturador | Operador piloto | Formularios, captura, evidencias |
   | Aprobador | Supervisor piloto | Revision/aprobacion |
   | Integrador | Tecnico API | API keys y bulk sync |

5. Usar datos de prueba sin informacion sensible.
6. Registrar cada resultado como `Aprobado`, `Observado`, `Rechazado` o
   `Pendiente`.

## UAT-01 Login, sesion y seleccion de proyecto

### Pasos

1. Entrar al frontend local.
2. Iniciar sesion con usuario piloto.
3. Confirmar que aparece el proyecto correcto.
4. Cambiar de modulo desde el menu.
5. Cerrar sesion y volver a entrar.

### Evidencia

- usuario/rol usado;
- proyecto visible;
- captura o nota del menu disponible;
- fecha y hora.

### Criterio de aprobacion

El usuario entra, ve solo proyectos autorizados y el menu coincide con sus
permisos.

## UAT-02 Constructor de formularios

### Pasos

1. Entrar como administrador o configurador.
2. Crear o editar un formulario piloto.
3. Agregar campos obligatorios, selectores, campos numericos y texto.
4. Guardar plantilla.
5. Confirmar que el formulario queda disponible en runtime.

### Evidencia

- nombre del formulario;
- lista de campos principales;
- captura o identificador de plantilla.

### Criterio de aprobacion

La plantilla se crea/edita sin tocar codigo y queda lista para captura.

## UAT-03 Captura de registros y evidencias

### Pasos

1. Entrar como capturador.
2. Abrir el formulario piloto.
3. Diligenciar campos obligatorios.
4. Adjuntar evidencia cuando aplique.
5. Guardar el registro.

### Evidencia

- identificador del registro;
- usuario que captura;
- evidencia adjunta o nombre de archivo de prueba.

### Criterio de aprobacion

El registro se guarda con validaciones correctas y las evidencias quedan
asociadas.

## UAT-04 Consulta de registros

### Pasos

1. Ir al modulo de registros.
2. Buscar el registro creado.
3. Abrir detalle.
4. Confirmar datos, estado y evidencias.

### Evidencia

- identificador de registro;
- filtro usado;
- resultado encontrado.

### Criterio de aprobacion

El registro aparece y conserva la informacion capturada.

## UAT-05 Flujo de aprobacion

### Pasos

1. Configurar o confirmar flujo de aprobacion.
2. Enviar registro a revision.
3. Entrar como aprobador.
4. Aprobar, rechazar o devolver segun escenario.
5. Revisar historial.

### Evidencia

- flujo usado;
- aprobador;
- accion tomada;
- estado final;
- historial visible.

### Criterio de aprobacion

El flujo respeta orden, responsables y deja trazabilidad.

## UAT-06 Reportes

### Pasos

1. Entrar como supervisor.
2. Abrir reportes.
3. Filtrar por proyecto/formulario/fecha.
4. Exportar CSV/XLSX si aplica.
5. Comparar totales con registros creados.

### Evidencia

- filtro usado;
- archivo exportado;
- total esperado vs total obtenido.

### Criterio de aprobacion

El reporte muestra datos correctos y exporta informacion util.

## UAT-07 Mapas y georreferenciacion

### Pasos

1. Crear o usar registros con coordenadas.
2. Abrir modulo de mapas.
3. Confirmar puntos visibles.
4. Revisar detalle del punto.

### Evidencia

- identificador del registro;
- coordenadas de prueba;
- resultado en mapa.

### Criterio de aprobacion

Los registros georreferenciados aparecen en mapa y se pueden consultar.

## UAT-08 Administracion de usuarios

### Pasos

1. Entrar como administrador.
2. Crear o revisar usuario piloto.
3. Corregir correo de prueba.
4. Reiniciar contrasena o MFA cuando aplique.
5. Confirmar que la accion pide confirmacion.

### Evidencia

- usuario afectado;
- accion realizada;
- confirmacion visible;
- resultado posterior.

### Criterio de aprobacion

El administrador puede recuperar acceso sin exponer contrasenas ni saltarse
permisos.

## UAT-09 API keys

### Pasos

1. Entrar como administrador/integrador.
2. Crear API key para proyecto.
3. Probar llamada controlada.
4. Confirmar perfil de limite configurado.
5. Revocar API key.

### Evidencia

- nombre de API key;
- endpoint probado;
- resultado de llamada;
- revocacion confirmada.

### Criterio de aprobacion

La API key permite integracion controlada y puede revocarse con trazabilidad.

## UAT-10 Sincronizacion bulk

### Pasos

1. Preparar lote pequeno de prueba.
2. Enviar lote por API o panel disponible.
3. Revisar estado del job.
4. Confirmar creados/fallidos/reintentos.
5. Reenviar lote para validar idempotencia cuando aplique.

### Evidencia

- identificador del lote;
- total enviado;
- creados;
- fallidos;
- errores detectados.

### Criterio de aprobacion

El sistema procesa lotes sin duplicar datos y muestra errores accionables.

## UAT-11 Auditoria

### Pasos

1. Ejecutar acciones sensibles: login, cambio de correo, reset, API key,
   aprobacion.
2. Abrir auditoria.
3. Buscar eventos por usuario, modulo o fecha.

### Evidencia

- evento auditado;
- usuario;
- fecha;
- modulo.

### Criterio de aprobacion

Las acciones sensibles quedan registradas y consultables.

## UAT-12 Metricas y salud operativa

### Pasos

1. Abrir dashboard/metrica operativa.
2. Revisar solicitudes, errores, latencias o estado disponible.
3. Consultar health/readiness si aplica.
4. Confirmar que no existan alertas bloqueantes.

### Evidencia

- pantalla o resumen de metricas;
- estado de health/readiness;
- hallazgos operativos.

### Criterio de aprobacion

El equipo puede saber si el sistema esta funcionando y detectar fallos
principales.

## Reglas de decision

| Resultado | Cuando usarlo |
| --- | --- |
| Aprobado | El flujo cumple y no deja riesgo relevante. |
| Observado | Funciona, pero requiere mejora o ajuste menor. |
| Rechazado | No cumple el objetivo funcional o genera riesgo. |
| Pendiente | No se ejecuto o faltaron datos/usuario/ambiente. |

## Cierre recomendado

1. Todos los UAT criticos deben estar `Aprobado` u `Observado` aceptado.
2. Ningun hallazgo `Bloqueante` puede quedar abierto.
3. Hallazgos `Alta` deben corregirse antes de produccion.
4. Hallazgos `Media` y `Baja` pueden pasar a backlog si el responsable lo
   acepta.
5. Generar nueva entrega con `.\scripts\make-delivery.cmd` despues de corregir
   hallazgos.
6. Generar resumen de cierre con `.\scripts\summarize-uat-evidence.cmd`.
