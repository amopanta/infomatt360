# Verificación del dispositivo móvil en formularios

El campo interno `FINGERPRINT` solicita una verificación WebAuthn del **usuario que diligencia**. El móvil puede usar huella, rostro o PIN, según sus capacidades y configuración. InfoMatt360 no recibe una imagen de la huella ni identifica biométricamente al participante. Para capturar la huella real de un participante se requiere un lector externo y una integración distinta.

## Uso

1. El diseñador agrega **Verificación del dispositivo** al formulario y, si corresponde, lo marca obligatorio.
2. El gestor abre el formulario con sesión iniciada, en HTTPS y con internet.
3. En el primer uso, pulsa **Registrar este móvil** o **Verificar en este móvil** y completa el registro del autenticador local. Después puede verificar con el dispositivo registrado. Si cambia de móvil, usa **Registrar este móvil**.
4. El servidor valida el reto WebAuthn, origen, dominio, clave pública y verificación del usuario. Guarda un identificador de evento temporal en la respuesta del campo.
5. Al enviar, el servidor comprueba que el evento pertenece al mismo usuario, formulario y campo, que no venció y que no se usó en otro registro. El evento queda vinculado al registro.

La verificación dura cinco minutos desde el inicio del reto. Si vence, el gestor debe verificar de nuevo. Formularios con este campo no entran en la cola de envío sin conexión; el borrador permanece local si falla el transporte.

## Datos y límites

- Se guardan la clave pública del autenticador, contador de firmas y metadatos del evento. No se guardan plantillas ni imágenes biométricas.
- WebAuthn con `userVerification=required` confirma una acción local del dispositivo, pero no garantiza que se usó exclusivamente una huella; el sistema puede pedir rostro o PIN.
- La verificación corresponde a la cuenta del gestor. No acredita la identidad ni el consentimiento del participante.
- El campo requiere una sesión; los formularios que lo contienen no se publican mediante enlaces públicos.
- Los eventos no se pueden duplicar para generar registros nuevos: al duplicar una respuesta, el campo queda vacío y debe verificarse de nuevo.
- El XLSForm maestro representa este tipo como `text` con `appearance=infomatt_device_verification`. Es una extensión de InfoMatt360; otras plataformas pueden mostrarlo como texto. La antigua marca `image`/`appearance=fingerprint` se sigue reconociendo al importar.

## Despliegue

Ejecutar la migración Alembic `0079_device_verification` antes de activar el backend. La dependencia Python `webauthn` se instala desde `backend/requirements.txt`. El origen y el dominio WebAuthn se derivan de `FRONTEND_URL`; el sitio móvil debe usarse por HTTPS.
