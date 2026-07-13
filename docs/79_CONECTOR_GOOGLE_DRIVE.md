# Conector Google Drive (OAuth)

## Objetivo

Permitir subir evidencias/backups a Google Drive por proyecto, usando el
campo `provider="gdrive"` que `StorageProfile` ya soportaba desde antes de
esta fase (`credentials_json` estaba previsto para esto).

## Estado por defecto: inactivo

Sin `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET` /
`GOOGLE_OAUTH_REDIRECT_URI` configurados en el backend, todos los metodos
que requieren la integracion (`build_authorization_url`,
`exchange_code_for_tokens`) rechazan con `400 Bad Request` ("El conector de
Google Drive no esta configurado en este servidor") en vez de fallar de
forma confusa mas adelante en el flujo OAuth.

## Diseno

- Usa REST directo con `httpx` en vez de `google-api-python-client`, para
  no agregar esa dependencia pesada al backend solo por este conector
  opcional.
- El `state` del flujo OAuth se firma con HMAC-SHA256
  (`sign_state`/`verify_state`, usando `settings.secret_key`) para evitar
  que se falsifique el `project_id` al que se conecta la cuenta.
- Los tokens OAuth (access + refresh) se guardan cifrados con Fernet
  (`encrypt_text`/`decrypt_text`, `app.core.security`) en
  `StorageProfile.oauth_tokens_encrypted`, columna que **nunca** se expone
  en `StorageProfileRead`.
- El access token se refresca automaticamente
  (`_valid_access_tokens`) cuando falta menos de 60 segundos para que
  expire, usando el `refresh_token` guardado.

## Flujo OAuth

1. `GET /api/v1/storage/oauth/gdrive/authorize?project_id=...` — requiere
   el permiso `storage.manage` sobre el proyecto, devuelve la URL de
   autorizacion de Google.
2. El usuario autoriza en Google y vuelve a
   `GET /api/v1/storage/oauth/gdrive/callback?code=...&state=...` — sin
   autenticacion (es un redirect de Google, no una llamada de la SPA);
   la seguridad viene de la firma HMAC del `state`, no de la sesion.
3. El callback intercambia el `code` por tokens y crea/actualiza el
   `StorageProfile` del proyecto con `provider="gdrive"`.

**Correccion de seguridad**: originalmente el paso 1 solo exigia
pertenencia activa al proyecto (`user_has_project_access`), igual que
`POST /storage/s3/connect` -- ver la nota de correccion de seguridad en
[89_ALMACENAMIENTO_S3_BOVEDA_MULTIMEDIA.md](89_ALMACENAMIENTO_S3_BOVEDA_MULTIMEDIA.md)
para el detalle del impacto (cualquier miembro del proyecto podia
conectar su propia cuenta de Drive como destino por defecto).

## Activarlo

Crear credenciales OAuth de un proyecto real en Google Cloud Console (tipo
"Aplicacion web", scope `drive.file`) y configurar las tres variables de
entorno mencionadas arriba en `backend/.env`. Sin esto, el conector
permanece inactivo sin afectar el resto del sistema.

## Pantalla en el frontend

Pestaña "Google Drive" en `frontend/src/modules/admin/StorageApp.tsx`
(ruta `/admin/storage`, ver
[89_ALMACENAMIENTO_S3_BOVEDA_MULTIMEDIA.md](89_ALMACENAMIENTO_S3_BOVEDA_MULTIMEDIA.md)):
el boton "Conectar Google Drive" pide la URL de autorizacion y la abre en
una pestaña nueva (`window.open`), ya que el callback de Google es una
ruta de backend que no vuelve a la SPA. El administrador completa el
consentimiento en esa pestaña y luego usa "Actualizar lista" en la
pantalla de InfoMatt360 para confirmar que el destino quedo conectado.

## Limites conocidos

- Solo sube archivos (`upload_file`); no lista ni descarga desde Drive
  todavia.
- Una cuenta de Google Drive por proyecto (no por organizacion).
- El callback OAuth (`GET /oauth/gdrive/callback`) devuelve el
  `StorageProfileRead` como JSON crudo en vez de redirigir a una pantalla
  de InfoMatt360; por eso el flujo de la UI abre una pestaña aparte en vez
  de esperar una redireccion de vuelta a la SPA.
