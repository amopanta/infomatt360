# Certificacion con Formulario Complejo

## Objetivo
Usar el formulario Plan de Inversion como prueba exigente del Builder y Runtime.

## Hallazgos del archivo recibido

El XLSForm analizado tiene aproximadamente:

```text
469 filas en survey
609 filas en choices
17 grupos
14 repeats
259 calculos
58 enteros
53 textos
24 select_one
36 reglas relevant
15 filtros choice_filter
411 campos requeridos
354 calculos/pulldata/expresiones
```

Esto lo convierte en una plantilla ideal para certificar el motor de formularios.

## Riesgos que debe resolver InfoMatt360

### 1. Carga rapida
El formulario debe cargarse por paginas o secciones y no bloquear la vista completa.

### 2. Repeats editables
Los grupos agregar deben permitir cambiar cantidades anteriores. Si el usuario pasa de 6 productos a 5, el sistema debe recalcular y remover el item sobrante sin dejar basura logica.

### 3. Pulldata dinamico
Las bases externas no deben quedar congeladas dentro del formulario. Deben poder refrescarse desde URL, Google Drive, SharePoint, API o archivo administrado.

### 4. Publicacion masiva
Debe existir accion masiva para publicar formularios seleccionados o aplicar una misma fuente externa a varios formularios.

### 5. Recalculo inteligente
Al cambiar un campo base, el Runtime debe recalcular dependientes sin bloquear al usuario.

## Decision tecnica
Se agrega el modulo External Data para representar fuentes externas reutilizables.

```text
external_data_sources
form_data_source_bindings
bulk_publish_jobs
```

## Pendientes tecnicos

- motor de sincronizacion de fuente externa;
- UI de acciones masivas;

## Avance External Data

Rutas disponibles bajo `/api/v1/external-data`:

- crear y listar fuentes externas;
- vincular una fuente con una plantilla;
- encolar publicacion masiva de plantillas.

Todas las operaciones validan la asignacion del usuario al proyecto. Los
bindings y trabajos masivos rechazan mezclas de fuentes o plantillas entre
proyectos distintos.

## Evaluacion Pulldata

El motor de expresiones admite la firma compatible con XLSForm:

```text
pulldata('municipios', 'nombre', 'codigo', ${municipio_id})
```

Runtime entrega las fuentes sincronizadas mediante `context.__pulldata__`. Cada
alias puede contener directamente una lista de filas o un objeto versionado con
la forma `{ "version": "...", "rows": [...] }`. Los datos permanecen fuera de
la plantilla y pueden refrescarse sin recompilar el formulario.

Las versiones normalizadas se guardan como snapshots. Runtime obtiene la ultima
version de todas las fuentes vinculadas mediante:

```text
GET /api/v1/external-data/runtime-cache/{template_id}
```
