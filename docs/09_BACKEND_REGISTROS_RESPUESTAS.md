# Backend - Registros y Respuestas

## Objetivo
Crear el modulo base para almacenar respuestas de formularios conectadas a proyecto, formulario, participante y usuario.

## Archivos agregados

```text
backend/app/models/records.py
backend/app/schemas/records.py
backend/app/services/record_service.py
backend/app/api/v1/records.py
backend/alembic/versions/0006_records_base.py
```

## Capacidades iniciales

- crear registro o respuesta;
- asociar registro a proyecto;
- asociar registro a formulario;
- asociar registro a participante;
- identificar canal de origen;
- guardar payload JSON flexible;
- guardar creador;
- crear evento inicial de historial;
- listar registros por proyecto;
- filtrar registros por participante;
- consultar eventos del registro.

## Endpoints

```text
POST /api/v1/records/
GET /api/v1/records/project/{project_id}
GET /api/v1/records/{record_id}/events
```

## Pendientes

- actualizacion de registros;
- flujo formal de aprobacion;
- validacion contra estructura del formulario;
- IA de coherencia del dato;
- auditoria ampliada;
- resolucion de conflictos offline;
- hash de contenido;
- version de formulario usada en la captura.
