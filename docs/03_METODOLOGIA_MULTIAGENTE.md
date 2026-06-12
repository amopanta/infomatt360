# Metodologia de Trabajo Multiagente - InfoMatt360

## Objetivo
Organizar el desarrollo de InfoMatt360 mediante un esquema de agente director y roles tecnicos especializados, manteniendo documentacion, trazabilidad, comentarios de codigo y pruebas desde el inicio.

## Modelo de trabajo

```text
Agente Director
  Arquitectura
  Backend
  Base de datos
  Frontend web
  Android
  Escritorio
  Integraciones
  IA/OCR
  QA y pruebas
  Documentacion
```

## Reglas obligatorias

1. Todo modulo nuevo debe tener documentacion.
2. Todo codigo debe tener comentarios donde la logica no sea obvia.
3. Todo endpoint debe quedar documentado.
4. Todo cambio relevante debe tener prueba o criterio de validacion.
5. Todo archivo critico debe tener proposito claro.
6. Toda decision tecnica debe registrarse en docs.
7. Ningun modulo debe romper la arquitectura multi proyecto.
8. Ningun dato debe saltarse permisos, auditoria o trazabilidad.

## Roles

### Agente Director
Coordina prioridades, evita desviaciones y mantiene coherencia del producto.

### Agente Arquitectura
Define limites, capas, patrones, integraciones y decisiones estructurales.

### Agente Backend
Construye API, servicios, seguridad, sincronizacion, reglas y procesos.

### Agente Base de Datos
Define modelos, migraciones, indices, aislamiento de proyectos y rendimiento.

### Agente Frontend Web
Construye la consola web administrativa y operativa.

### Agente Android
Construye la aplicacion de campo offline first.

### Agente Escritorio
Construye el cliente de escritorio para oficina, offline, cargas masivas, actas e impresion.

### Agente Integraciones
Construye conectores no-code, API externas, base espejo, GIS y BI.

### Agente IA/OCR
Construye validacion inteligente, OCR, analisis documental y reportes ejecutivos.

### Agente QA
Define y ejecuta pruebas funcionales, carga, seguridad y regresion.

### Agente Documentacion
Mantiene manuales, bitacora, arquitectura, instalacion, despliegue y solucion de errores.

## Orden inicial de construccion

1. Arquitectura y modelo de datos.
2. Backend base.
3. Autenticacion y proyectos.
4. Usuarios, roles y permisos.
5. Formularios base.
6. Participantes y registros.
7. Evidencias y storage.
8. Sincronizacion.
9. Reportes.
10. Integraciones.

## Criterio de aceptacion de cada modulo

Cada modulo se considera aceptado cuando tenga:

- codigo funcional;
- README o documento tecnico;
- endpoints documentados si aplica;
- pruebas o caso de validacion;
- comentarios en logica clave;
- registro de riesgos o pendientes.
