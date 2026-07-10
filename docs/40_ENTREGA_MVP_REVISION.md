# Entrega MVP para revision

## Estado

InfoMatt360 queda en estado MVP avanzado para revision local.

Avance estimado: **98%**.

## Alcance incluido

- autenticacion con access token en memoria y refresh token en cookie httpOnly;
- refresh tokens rotados y revocacion de sesiones;
- recuperacion y cambio de contrasena;
- administracion de usuarios por administrador;
- correccion de correo;
- reinicio de contrasena temporal;
- MFA TOTP con codigos de recuperacion;
- auditoria de acciones sensibles;
- selector de proyecto;
- Builder con catalogo de campos validado;
- layout visual basico;
- Runtime web;
- campos dinamicos, firmas, archivos, coordenadas y repetidores;
- persistencia de registros;
- busqueda, filtros, paginacion y detalle de registros;
- exportacion CSV segura para Excel;
- dashboard operativo;
- reportes por formulario/estado;
- exportacion XLSX sin dependencias externas;
- mapa operativo SVG con coordenadas Runtime/GIS;
- vista de auditoria;
- datos demo idempotentes;
- smoke test de demo end-to-end;
- validacion CORS local de navegador;
- contrato de rutas frontend y permisos administrativos;
- scripts Windows de arranque, pruebas, health, demo y preflight;
- readiness operativo `/api/v1/health/ready`.

## Como revisar

```powershell
Copy-Item .env.example backend\.env
.\scripts\seed-demo.cmd
.\scripts\dev-backend.cmd
```

En otra terminal:

```powershell
.\scripts\dev-frontend.cmd
```

Si el backend ya esta encendido:

```powershell
.\scripts\check-health.cmd
.\scripts\check-demo.cmd
```

Validacion completa:

```powershell
.\scripts\preflight.cmd
```

## Credenciales demo

```text
Usuario: admin@infomatt360.demo
Clave: Demo12345!
Proyecto: demo-project-infomatt360
```

## Evidencia automatizada actual

```text
Backend: 178 pruebas automatizadas
Frontend: 26 pruebas Vitest y build Vite validado
TypeScript: 65 archivos TS/TSX con sintaxis validada offline
Preflight: OK para revision local
```

## Pendientes conocidos

- configurar PostgreSQL, SMTP, HTTPS y `SECRET_KEY` fuerte para produccion;
- agregar pruebas visuales con Playwright/Cypress;
- preparar instalador o contenedor Docker si se decide una entrega empaquetada.

## Criterio de salida MVP

El MVP se considera listo para revision cuando:

- `.\scripts\preflight.cmd` termina OK;
- `.\scripts\check-demo.cmd` valida endpoints demo con backend encendido;
- el usuario demo puede entrar y navegar Dashboard, Registros, Reportes, Mapas, Auditoria y Usuarios;
- las advertencias de readiness son conocidas y aceptadas para ambiente de desarrollo.
