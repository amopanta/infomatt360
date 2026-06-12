# Backend - Almacenamiento Configurable

## Objetivo
Permitir que cada proyecto configure donde guardar sus archivos y evidencias.

## Archivos agregados

```text
backend/app/models/storage.py
backend/app/schemas/storage.py
backend/app/services/storage_service.py
backend/app/api/v1/storage.py
```

## Capacidades iniciales

- crear perfil de almacenamiento por proyecto;
- listar perfiles por proyecto;
- definir proveedor local, S3, MinIO o externo;
- configurar ruta base;
- configurar bucket;
- configurar endpoint;
- guardar credenciales en JSON;
- definir limite de peso por archivo;
- marcar perfil por defecto.

## Endpoints

```text
POST /api/v1/storage/
GET /api/v1/storage/project/{project_id}
```

## Pendientes

- cifrar credenciales;
- probar conexion;
- carga real de archivos;
- integracion MinIO;
- integracion Google Drive;
- enlaces temporales;
- politica de retencion;
- auditoria de uso.
