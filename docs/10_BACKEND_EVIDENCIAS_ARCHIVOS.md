# Backend - Evidencias y Archivos

## Objetivo
Crear el modulo base para registrar evidencias y archivos asociados a proyectos, participantes y registros.

## Archivos agregados

```text
backend/app/models/files.py
backend/app/schemas/files.py
backend/app/services/file_service.py
backend/app/api/v1/files.py
```

## Capacidades iniciales

- registrar metadatos de archivo;
- asociar archivo a proyecto;
- asociar archivo a participante;
- asociar archivo a registro;
- clasificar tipo de evidencia;
- guardar proveedor de almacenamiento;
- guardar ruta;
- guardar MIME;
- guardar peso;
- guardar checksum;
- guardar texto OCR;
- listar evidencias por proyecto;
- filtrar por participante o registro.

## Endpoints

```text
POST /api/v1/files/
POST /api/v1/files/upload
GET /api/v1/files/project/{project_id}
```

## Pendientes

- descarga autenticada;
- MinIO o S3;
- Google Drive;
- limite de peso por proyecto;
- OCR automatico;
- visor PDF;
- editor PDF integrado;
- descarga masiva ZIP;
- enlaces temporales seguros.
