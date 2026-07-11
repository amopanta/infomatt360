# Paquete fuente de entrega

## Objetivo

Generar un ZIP de revision con el codigo fuente del MVP sin arrastrar archivos
locales pesados o sensibles.

## Comando

```powershell
.\scripts\make-release.cmd
```

Generar entrega completa validada:

```powershell
.\scripts\make-delivery.cmd -ProjectName "Piloto InfoMatt360" -Environment "Local"
```

## Salida

El ZIP se crea en:

```text
..\outputs
```

con nombres similares a:

```text
infomatt360-mvp-source-YYYYMMDD-HHMMSS.zip
infomatt360-mvp-source-YYYYMMDD-HHMMSS.sha256.txt
```

El archivo `.sha256.txt` permite verificar integridad del paquete. Incluye fecha de
generacion, tamano, numero de archivos y hash SHA256.

## Excluye

- `.git`
- `.venv`
- `node_modules`
- `dist`
- `__pycache__`
- `.pytest_cache`
- `uploads`
- archivos `.env`
- bases `*.db`
- bytecode Python

## Uso recomendado

Antes de generar paquete:

```powershell
.\scripts\preflight.cmd
.\scripts\make-status-report.cmd
```

Luego:

```powershell
.\scripts\make-release.cmd
```

## Verificacion de integridad

Para comparar manualmente el hash del ZIP:

```powershell
Get-FileHash -Algorithm SHA256 ..\outputs\infomatt360-mvp-source-YYYYMMDD-HHMMSS.zip
```

## Archivos complementarios

La entrega recomendada incluye:

- ZIP fuente `infomatt360-mvp-source-YYYYMMDD-HHMMSS.zip`;
- manifiesto `infomatt360-mvp-source-YYYYMMDD-HHMMSS.sha256.txt`;
- reporte `infomatt360-status-YYYYMMDD-HHMMSS.md`.
