# Revision funcional local

## Objetivo

Validar que InfoMatt360 pueda abrirse y operar localmente como sistema completo:
backend, frontend, base demo, autenticacion y modulos principales.

## Comando automatizado

Desde la raiz del proyecto:

```powershell
.\scripts\check-full-stack.cmd
```

Este comando:

1. levanta el backend local en `http://127.0.0.1:8000`;
2. levanta el frontend local en `http://127.0.0.1:5173`;
3. espera readiness del backend;
4. valida disponibilidad del frontend;
5. ejecuta smoke API con usuario demo;
6. apaga los procesos temporales al finalizar.

## Resultado de la ultima revision

Fecha de corte: 2026-07-03.

Estado: OK.

Validaciones automatizadas aprobadas:

- health backend;
- API v1 health;
- readiness backend;
- frontend disponible;
- login demo;
- sesion;
- dashboard;
- formularios;
- registros;
- reportes;
- mapas;
- historial de revision;
- listado de API keys;
- usuarios administrador;
- conteos de mensajes;
- inbox de mensajes;
- auditoria;
- metricas operativas.

## Credenciales demo

```text
Usuario: admin@infomatt360.demo
Clave: Demo12345!
Proyecto: demo-project-infomatt360
```

## Revision manual recomendada

Despues de que el comando automatizado pase, hacer una revision visual en el
navegador:

1. abrir `http://127.0.0.1:5173`;
2. iniciar sesion con el usuario demo;
3. recorrer el menu lateral;
4. confirmar que las pantallas carguen sin errores visibles;
5. crear o editar un formulario de prueba;
6. registrar una captura de prueba;
7. revisar que aparezca en registros, dashboard y auditoria;
8. probar exportacion de reportes;
9. revisar flujos de aprobacion;
10. revisar usuarios, API keys, sincronizacion bulk y metricas.

## Criterios de aceptacion

La revision funcional local se considera aprobada cuando:

- el comando `check-full-stack.cmd` termina en `Full stack OK`;
- el usuario demo puede iniciar sesion;
- el menu muestra las opciones segun permisos;
- los modulos principales responden;
- no hay errores visibles de carga;
- los datos demo se consultan correctamente;
- auditoria y metricas quedan accesibles para administracion.

## Validacion CORS de navegador

La prueba visual en navegador usa un origen web real. En desarrollo se validan
ambos origenes comunes de Vite:

- `http://localhost:5173`;
- `http://127.0.0.1:5173`.

Comando:

```powershell
.\scripts\check-browser-cors.cmd
```

Este punto evita que la API funcione por pruebas directas pero falle en el
navegador por preflight CORS.

## Si algo falla

1. Ejecutar `.\scripts\doctor.cmd`.
2. Ejecutar `.\scripts\prepare-demo.cmd`.
3. Ejecutar `.\scripts\check-demo-db.cmd`.
4. Repetir `.\scripts\check-full-stack.cmd`.
5. Si persiste el error, revisar logs del backend y el mensaje exacto del modulo.
