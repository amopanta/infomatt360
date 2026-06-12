# InfoMatt360 - Arquitectura Empresarial

Estado: version inicial

## 1. Objetivo
Definir la arquitectura base de InfoMatt360 como sistema operativo territorial unificado, modular, escalable, multi proyecto y preparado para operacion web, movil y escritorio.

## 2. Capas principales

### 2.1 Core Data / Backend
Responsable de datos, seguridad, permisos, proyectos, formularios, participantes, reglas, auditoria, sincronizacion, integraciones, almacenamiento, IA y reportes.

### 2.2 Web Console
Consola administrativa y operativa. Debe permitir administracion nacional, gestion de proyectos, formularios, participantes, registros, reportes, mapas, mesa de ayuda, configuracion, integraciones y auditoria.

### 2.3 Android Field App
Aplicacion de campo offline first. Debe permitir inicio de sesion con el mismo usuario del sistema, seleccion de proyecto, descarga de formularios, captura, borradores, cola de envio, firma, foto, video, GPS, escaneo, OCR y diagnostico del dispositivo.

### 2.4 Desktop App
Aplicacion de escritorio para trabajo offline, carga masiva, validacion, actas, impresion, exportaciones, sincronizacion, manejo documental y operacion pesada de oficina.

### 2.5 Integration Hub
Modulo no-code para conectar APIs, Excel, CSV, JSON, bases externas, Google Sheets, sistemas gubernamentales, KoBo, ODK, ActivityInfo, RIT, KOKAN u otros.

### 2.6 AI Engine
Motor de validacion, OCR, analisis documental, analisis cualitativo, analisis cuantitativo, deteccion de inconsistencias y generacion de reportes ejecutivos.

### 2.7 Reporting Engine
Modulo de reportes dinamicos, tablas, graficos, mapas, KPI, enlaces publicados, exportaciones, impresion y reportes ejecutivos.

## 3. Estrategia multi proyecto
Un proyecto representa un espacio operativo independiente. Cada proyecto puede tener formularios, participantes, usuarios, permisos, almacenamiento, correo, reportes, reglas, integraciones y base de datos propia o esquema aislado.

## 4. Administracion nacional
Debe existir un administrador nacional capaz de crear, suspender, auditar y monitorear proyectos sin mezclar datos operativos entre proyectos.

## 5. Estrategia de datos
Se evaluan dos modelos:

- base de datos independiente por proyecto;
- esquema independiente por proyecto en PostgreSQL.

La decision tecnica inicial sera soportar esquema por proyecto y dejar preparada la arquitectura para base dedicada en proyectos grandes.

## 6. Flujo general

1. El administrador nacional crea un proyecto.
2. El proyecto configura usuarios, formularios, almacenamiento, correo e integraciones.
3. Los usuarios operan desde web, Android o escritorio con la misma cuenta.
4. Los datos se capturan, validan, sincronizan y auditan.
5. La IA revisa coherencia, calidad y documentos.
6. Los registros aprobados alimentan reportes, mapas, actas, exportaciones e integraciones.

## 7. Diagrama logico

```text
InfoMatt360
  Core Data / Backend
    Auth
    Projects
    Forms
    Participants
    Records
    Workflow
    Sync
    Storage
    Audit
    Integrations
    AI
    Reports
  Web Console
  Android Field App
  Desktop App
  External Systems
```

## 8. Reglas arquitectonicas

- Todo modulo debe respetar proyecto, permisos y auditoria.
- Ningun dato critico debe pasar a reportes sin validacion.
- Toda sincronizacion debe dejar trazabilidad.
- Todo archivo debe tener metadata, propietario, proyecto, origen y hash.
- Toda integracion debe guardar historial de ejecucion.
- Toda configuracion sensible debe almacenarse cifrada.
