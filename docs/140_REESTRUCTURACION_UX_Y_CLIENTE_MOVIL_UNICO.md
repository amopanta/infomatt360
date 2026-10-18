# 140 — Reestructuración de experiencia y cliente móvil único

Fecha: 2026-10-17

## Objetivo

Que una persona sin formación técnica pueda crear y llenar formularios con
capacitación mínima, y dejar un solo cliente móvil oficial conectado al
backend principal.

## 1. Versiones móviles: decisión

Existían tres clientes de campo además de la web:

| Cliente | Qué era | Decisión |
|---|---|---|
| `mobile/` (este repo, Express + SQLite propia + APK con Capacitor) | Servidor y base de datos independientes (`usuarios`, `registros`, `plantillas`…). No compartía usuarios, formularios ni respuestas con el backend FastAPI: lo capturado ahí no llegaba a la plataforma. | **Retirado** del repositorio, junto con `install.sh` y `deploy-mobile.sh` (instaladores exclusivos de ese módulo). Casos y territorios ya existen en el backend principal (`/cases`, `/territories`). |
| `amopanta/infomatt360-mobile` (React Native / Expo) | App nativa con SQLite local y cola offline, pensada para el backend principal. | **App móvil oficial.** Se corrigieron sus contratos con el backend (ver abajo). |
| `desktop/` (Electron) | Envoltura de escritorio de la web con impresión y cola offline. | Se conserva; es complementaria, no móvil. |

La PWA del `frontend/` sigue siendo válida desde el navegador del celular.

### Correcciones en `infomatt360-mobile`

- La app se cerraba al abrir: `AppNavigator` declaraba un `useEffect` después
  del `return` de "Cargando…" (número de hooks distinto entre renders).
- Formularios: usaba `GET /forms/project/{id}` y `GET /forms/{id}` (modelo
  antiguo, sin páginas). Ahora usa `GET /builder/templates/{project_id}` y
  `GET /runtime/template/{id}`, igual que la web, y traduce tipos del backend
  (`TEXT`, `SELECT`, `IMAGE`…) a los del renderizador.
- Participantes: la lista llega como arreglo plano y los formularios del
  participante salen de `GET /participants/{id}/activities` (no existía
  `/participants/{id}/forms`).
- Sincronización (`POST /runtime/session/bulk-save`): cada registro ahora
  incluye `project_id`/`template_id` y los valores van como
  `{field_name, field_value_json}` con JSON en texto. Antes el servidor
  rechazaba el lote completo con 422. Un registro con evidencias sin subir
  espera al siguiente ciclo.
- Evidencias (`POST /files/upload`): campo `upload` y `asset_type`
  obligatorios; se guarda el id del archivo en el servidor.
- MFA: el reto llega como `mfa_challenge_token` y se verifica con
  `{challenge_token, code}`.
- Los identificadores del backend son UUID (texto). Las tablas de caché
  local (`form_templates`, `participants`) se recrean una vez
  (`PRAGMA user_version = 2`) sin tocar la cola de capturas.

### Pendiente operativo (producción)

`docs/136_DNS_SSL_PRODUCCION.md` incluía un bloque nginx `/mobile-api/` hacia
`127.0.0.1:3000` (el Express retirado). Si el servicio `infomatt360-mobile`
sigue activo en el VPS, revisar si tiene capturas por rescatar, luego
detenerlo (`systemctl disable --now infomatt360-mobile`) y quitar ese bloque
de nginx.

## 2. Navegación por tareas

`frontend/src/components/AppShell.tsx`: de 4 grupos y 32 opciones mezcladas a
seis áreas según lo que la persona quiere hacer:

1. **Inicio** — Inicio, Llenar formularios.
2. **Formularios** — Crear y editar, Actas, Formularios abiertos, Importar desde Excel (XLSForm).
3. **Datos** — Registros, Participantes, Actividades aplicadas, Evidencias, Mapas.
4. **Revisión y reportes** — Flujos de aprobación, Mensajes, Reportes, Auditoría, Métricas.
5. **Configuración** (cerrado por defecto) — Usuarios, Equipos, Marca, Correo, WhatsApp, Mi seguridad.
6. **Avanzado** (cerrado por defecto) — Carga masiva Excel, Sincronización, Claves de API, Donantes, ERP, Almacenamiento, Auditoría IA, Gobernanza, Copias de seguridad, Base espejo.

Cada opción conserva su filtro de permisos: un encuestador de campo ve solo lo
que puede usar. Las rutas no cambiaron. Los textos nuevos están en el bloque
`ux` de `frontend/src/i18n/locales/{es,en}.json`.

La pantalla de Inicio agrega accesos grandes ("Crear un formulario", "Llenar
un formulario", "Ver respuestas", "Revisar y aprobar") filtrados por permiso.

## 3. Constructor de formularios

- **Asistente de inicio** al crear: En blanco, Plantilla de caracterización,
  Desde un PDF, Describir con IA, Importar Excel (XLSForm).
- **Paleta en dos niveles** (`fieldCatalog.ts`, `BuilderPalette.tsx`): 14
  preguntas de uso frecuente con icono siempre visibles; el resto en "Más
  tipos de pregunta" por categoría, con buscador. Nombres sin jerga ("Elegir
  varias opciones" en vez de `MULTISELECT`; "Identificador único" en vez de
  UUID).
- La tarjeta de cada pregunta muestra el tipo legible; **nombre técnico** y
  código del tipo pasan a "Opciones avanzadas".
- **Vista previa real** (`BuilderPreview.tsx`) en ancho de celular o
  computador, interactiva para probar las condiciones de visibilidad; no
  guarda respuestas. Antes el botón solo mostraba un mensaje.
- **Borrar y reordenar** preguntas ya guardadas mientras el formulario no
  tenga respuestas (antes quedaban bloqueadas aunque fuera un borrador).
  Botones ↑/↓ además de arrastrar. Con respuestas: no se borra, pero sí se
  puede reordenar.
- El texto de ayuda de una pregunta nueva ya no se llena con la descripción
  del catálogo (aparecía a quien llenaba el formulario).

### Backend nuevo

- `DELETE /api/v1/builder/components/detail/{component_id}` — elimina la
  pregunta y la fila/columna que queden vacías. Rechaza con 422 si el
  formulario ya tiene respuestas. Requiere `builder.write`.
- `PUT /api/v1/builder/templates/detail/{template_id}/component-order`
  `{component_ids: [...]}` — aplica el orden a preguntas y filas de layout.
  Rechaza ids ajenos o repetidos.

## 4. Otras correcciones

- **Carga por pantalla** (`main.tsx` con `React.lazy`): el archivo principal
  pasó de ~1.220 KB a ~401 KB; cada módulo se descarga al abrirlo.
- **Sesión perdida al recargar**: dos renovaciones simultáneas del token
  (StrictMode o varias pantallas con 401) presentaban el mismo refresh token
  rotado y el servidor invalidaba la sesión. `refreshAccessToken` ahora
  comparte una sola petición en curso.
- `backend/tests/test_whatsapp.py`: 4 pruebas rechazaban registros sin el
  concepto de no aprobación, que hoy es obligatorio; se agregó `notes`.

## Validación

- Backend: 496 pruebas aprobadas (incluye `tests/test_builder_component_edit.py`, 2 nuevas).
- Frontend: TypeScript sin errores, 111 pruebas aprobadas (incluye `fieldCatalog.test.ts`), build Vite/PWA correcto.
- App Expo: `tsc --noEmit` sin errores y recorrido completo en emulador Android (ver sección 5). Falta teléfono físico.
- Recorrido manual local (demo SQLite, `admin@infomatt360.demo`): crear
  formulario desde el asistente, vista previa con pregunta condicional,
  guardar, editar, eliminar una pregunta, reordenar, recargar y confirmar que
  los cambios y la sesión persisten.

## Pendiente

- Retirar el servicio Express del VPS (ver "Pendiente operativo").
- Evaluar subir la escala tipográfica base (`--font-size-base: 12px`) para
  mejorar la lectura de personas sin experiencia.

## 5. Pruebas de la app móvil en emulador Android (2026-10-17)

Recorrido real en un emulador Pixel 6 / Android 14 con Expo Go, contra el
backend local con datos demo. Se capturó sin conexión, se reconectó y se
verificó en el servidor cada valor y cada archivo.

### Errores encontrados y corregidos

| Error | Efecto en campo | Corrección |
|---|---|---|
| `uuid` v14 usa `crypto.getRandomValues`, inexistente en React Native | **La app se cerraba al abrir cualquier formulario** | `randomUUID` de `expo-crypto` (ya se usaba en el proyecto); se retira `uuid` |
| El backend nunca devolvía el refresh token a la app | Sesión perdida al cerrar la app y al vencer el token (sin señal, el encuestador quedaba fuera) | Modo nativo: con `X-Client-Platform: native` y **sin** `Origin` el refresh va en el cuerpo; la web sigue con cookie httponly. Un navegador no puede usar este modo porque siempre envía `Origin` |
| La "compresión" de fotos truncaba los bytes del JPEG | Fotos > 2 MB llegaban **corruptas** | Recodificación real con `expo-image-manipulator` (lado mayor 1920 px, calidad 0.7 → 0.4); si falla se conserva la original |
| Fotos adjuntas se subían antes de existir el registro | Evidencias sueltas, **sin vínculo** al registro | Orden: fotos de campo → registro → adjuntos con `record_id` del servidor (`queued_records.server_record_id`) |
| Fotos de campo viajaban como `{uri: "file://…"}` | El servidor guardaba una ruta del teléfono | Se envían como `{file_asset_id, name, mime_type, size_bytes}`, igual que la web |
| Firma en base64 dentro del registro | Registros pesados y formato distinto al de la web | Se guarda como PNG y se sube como `SIGNATURE` |
| Sí/No llegaba como texto `"true"` | Reportes y filtros lo trataban distinto a la web | Se envía como booleano según el tipo del backend |
| Fecha con `toISOString()` (UTC) | En Colombia, de noche se guardaba el día siguiente y se mostraba el anterior | Fecha local `YYYY-MM-DD`; verificado a las 20:36 hora de Bogotá |
| Aviso "No hay formularios descargados" sin conexión | Mensaje falso aunque hubiera formularios guardados | Se consulta la caché local, no el estado aún vacío |
| `X-Project-Id` enviado en cada petición | El backend no lo usa; bloqueaba la versión web por CORS | Se deja de enviar |
| `DateTimePicker.onChange` obsoleto | Aviso en desarrollo | `onValueChange` / `onDismiss` |

Backend: `backend/app/api/v1/auth.py` (`_is_native_client`,
`_deliver_refresh_token`) y `backend/tests/test_auth_native_client.py`
(4 pruebas: login nativo, rotación, navegador con `Origin` rechazado, web sin cambios).

### Resultado verificado en el servidor

Registro capturado sin conexión y sincronizado al reconectar: texto, Sí/No
(booleano), opción, número, fecha, GPS `{lat, lng, accuracy}`, foto de
campo y firma como archivos (`IMAGE` / `SIGNATURE`), y foto adjunta con
`record_id`. Reenviar el mismo lote no duplica (idempotencia). La sesión se
mantiene al cerrar y abrir la app (solo pide PIN).

### Cómo repetir la prueba en este equipo

- SDK en `D:\Android\Sdk`, JDK portátil en `D:\Android\jdk`, AVD `InfoMatt360`
  en `D:\Android\avd`; aceleración con *Android Emulator Hypervisor Driver*.
- Emulador: `emulator -avd InfoMatt360` (variables `ANDROID_HOME`,
  `ANDROID_AVD_HOME`). La app apunta a `http://10.0.2.2:8000/api/v1`, que es el
  `localhost` del equipo visto desde el emulador.
- App: `npx expo start --android` en el repositorio móvil (instala Expo Go).

### Pendiente

- Probar en un teléfono físico con la cámara real (fotos > 2 MB) y huella.
- Generar un APK de desarrollo/producción con EAS cuando se publique.
