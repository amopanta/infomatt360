# Backend - IA, OCR y Analisis Ejecutivo

## Objetivo
Crear la base para validacion inteligente, OCR, analisis cualitativo, analisis cuantitativo y reportes ejecutivos.

## Archivos agregados

```text
backend/app/models/ai.py
backend/app/schemas/ai.py
backend/app/services/ai_service.py
backend/app/api/v1/ai.py
backend/alembic/versions/0017_ai_ocr.py
```

## Capacidades iniciales

- registrar validacion IA por proyecto;
- asociar validacion a registro o archivo;
- registrar resultado OCR;
- guardar texto OCR y metadata;
- crear analisis ejecutivo;
- guardar resumen y metricas en JSON;
- validar acceso al proyecto antes de operar.

## Endpoints

```text
POST /api/v1/ai/checks
GET /api/v1/ai/checks/{project_id}
POST /api/v1/ai/ocr
POST /api/v1/ai/analysis
```

## Tipos previstos

- data_quality;
- consistency;
- document_review;
- signature_check;
- ocr_extract;
- executive_summary;
- qualitative_analysis;
- quantitative_analysis.

## Pendientes

- motor IA real;
- OCR con Tesseract o proveedor externo;
- validacion de coherencia contra formulario;
- bloqueo de aprobacion si falla IA;
- generacion PDF ejecutivo;
- integracion con reportes dinamicos.
