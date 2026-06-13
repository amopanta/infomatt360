# Personalizacion y Backup Offline

## Capacidades agregadas

InfoMatt360 debe permitir:

- personalizar formularios por programa;
- validar backups de tablet o escritorio;
- comparar que registros llegaron al servidor;
- reenviar solo registros faltantes;
- generar reporte de enviados, faltantes y conflictos.

## Tablas agregadas

```text
form_themes
template_theme_bindings
offline_backup_imports
offline_backup_record_checks
```

## Personalizacion visual

Cada formulario puede tener:

```text
program_name
icon_name
primary_color
secondary_color
background_color
custom_css
```

## Backup offline

Flujo esperado:

```text
subir backup
comparar contra runtime_records
marcar enviados
marcar faltantes
reenviar pendientes
generar reporte
```

## Pendientes

- API de carga de backup;
- comparador por hash/local id;
- vista web de reporte;
- exportacion Excel/PDF.
