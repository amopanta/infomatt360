# Datos demo y arranque local

## Objetivo

Facilitar la revision del MVP sin crear manualmente proyecto, usuario,
formulario, registros, reportes, mapa y mensajes internos.

## Comando

```powershell
.\scripts\seed-demo.cmd
```

El comando es idempotente: puede ejecutarse varias veces y actualiza los mismos
identificadores demo sin duplicar proyecto, usuario, formulario ni registros.

## Credenciales

```text
Usuario: admin@infomatt360.demo
Clave: Demo12345!
Proyecto: demo-project-infomatt360
```

## Contenido creado

- proyecto demo activo;
- usuario administrador demo;
- rol demo con permisos amplios;
- formulario publicado de caracterizacion;
- tres registros Runtime con valores y coordenadas;
- capa GIS y punto manual;
- evidencia logica asociada a un registro;
- mensaje interno demo no leido;
- evento de auditoria de carga demo.

## Pantallas para validar

- `/` Dashboard
- `/records` Registros
- `/reports` Reportes y exportacion XLSX
- `/maps` Mapa operativo
- `/messages` Mensajes internos
- `/admin/users` Seguridad de usuarios

## Validacion API del demo

Con el backend encendido y los datos demo cargados:

```powershell
.\scripts\check-demo.cmd
```

El comando inicia sesion con el usuario demo y valida endpoints principales:
sesion, dashboard, formularios, registros, reportes, mapas, mensajes y auditoria.
