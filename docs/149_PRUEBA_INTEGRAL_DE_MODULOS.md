# 149. Prueba integral de módulos (2026-10-23)

Prueba previa al rediseño visual y al manual de usuario. Se hizo en la copia
local con la base demo (migración `0086`) y el usuario administrador demo. En
producción no se usaron contraseñas reales.

## 1. Recorrido de los 34 módulos del menú

Un script recorrió todas las opciones del menú. En cada una registró:
- si la pantalla carga;
- las peticiones al servidor con error (4xx, 5xx o red);
- los errores de JavaScript;
- los mensajes de error en pantalla.

**Resultado: los 34 módulos cargan.** No hubo peticiones con error, errores
de JavaScript ni mensajes de error.

| Grupo | Módulos |
|---|---|
| Inicio | Inicio, Llenar formularios |
| Formularios | Crear y editar, Actas, Formularios públicos, Importar XLSForm |
| Datos | Registros, Participantes, Actividades aplicadas, Evidencias, Mapas |
| Revisión y reportes | Equipos de campo, Flujos de aprobación, Mensajes, Planeador mensual, Reportes, Auditoría, Métricas |
| Configuración | Usuarios, Equipos de gestores, Marca, Correo, WhatsApp, Mi seguridad |
| Avanzado | Carga masiva Excel, Sincronización, Claves de API, Donantes, ERP, Almacenamiento, Auditoría IA, Gobernanza, Copias de seguridad, Base espejo |

## 2. Hallazgo y corrección: 153 textos sin traducir

Seis pantallas mostraban identificadores internos en vez de texto (por
ejemplo `admin.storage.s3Title`, `admin.xlsform.importTitle`):

| Pantalla | Claves faltantes | Causa |
|---|---|---|
| Almacenamiento | 54 | El cambio de i18n del 13-oct (`d6ecfae`) reemplazó los textos por claves sin agregarlas al diccionario |
| Importar XLSForm | 45 | Igual |
| Formularios públicos | 27 | Igual |
| Auditoría IA (conexiones de IA) | 22 | El commit `44f5795` guardó los textos en `admin.erp` y la pantalla los busca en `admin.aiAudit` |
| Base espejo | 4 | `common.*` nunca existió |
| Participantes | 1 | Igual |

**Corrección:**
- Se recuperaron del historial de git los textos originales en español: 120
  por emparejamiento de líneas del cambio `d6ecfae` y 22 movidos desde
  `admin.erp`. Se corrigieron tildes que faltaban en el original y cabeceras
  de tabla que habían quedado mal emparejadas.
- Se escribieron las 11 restantes, con sus variables (`{provider}`,
  `{fields}`…).
- Se agregó la versión en inglés de todas.
- **Prueba nueva:** `frontend/src/i18n/keys.test.ts` revisa que toda clave
  `t('…')` del código exista en `es.json` y `en.json`. Falla si se vuelve a
  dejar una pantalla sin texto; se comprobó que falla sin la corrección.

## 3. Pruebas automáticas

- Backend: 557 pruebas (suite completa del 19-oct), sin cambios desde
  entonces.
- Web: 131 pruebas, incluida la nueva de textos.

## 4. Lo que sigue

- **Rediseño visual módulo por módulo** (pedido del responsable): primero
  una propuesta en un par de módulos para aprobar la dirección visual, y
  luego el resto.
- **Manual de usuario con capturas**, al final, para que las imágenes
  muestren el diseño nuevo.
- **Página de descarga en `mobile-infomatt360.tecnomatt.com`**, cuando exista
  el instalador Android de la app (EAS).
