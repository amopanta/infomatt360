# Correo autoconfigurado

## Objetivo

Reducir la friccion de configurar un `MailProfile` (ver modulo de
mensajeria existente) sugiriendo automaticamente el servidor SMTP para
proveedores conocidos, y permitir probar el envio real antes de guardar la
cuenta.

## Por que no es autodiscovery generico

No se implementa el protocolo de autodiscovery real (RFC 6186 / Thunderbird
Autoconfig, que resuelve DNS/HTTPS por dominio): esa tecnica es fragil y
falla con frecuencia en proveedores corporativos con configuraciones no
estandar. En su lugar, `backend/app/services/mail_autoconfig_service.py`
mantiene una tabla estatica de proveedores conocidos
(`gmail.com`, `outlook.com`, `hotmail.com`, `office365.com`, `yahoo.com`)
con su host/puerto/TLS ya validados.

## Funciones

- `suggest_config(email)`: extrae el dominio del correo y devuelve la
  sugerencia de servidor si el dominio esta en la tabla conocida, o `None`
  si no (el usuario completa manualmente).
- `send_test_email(profile)`: envia un correo de prueba real usando
  `smtplib` contra el `MailProfile` ya guardado, con STARTTLS si
  `use_tls=true` y autenticacion si el perfil tiene usuario/clave. Devuelve
  `(exito, mensaje)` en vez de lanzar, para que el endpoint pueda reportar
  el detalle del fallo SMTP sin romper la peticion.

## Endpoints

Agregados sobre el router de mensajeria ya existente (`backend/app/api/v1/messages.py`), sin modelo nuevo:

| Metodo | Ruta | Detalle |
| --- | --- | --- |
| `GET` | `/api/v1/messages/profiles/autoconfig?email=...` | Devuelve `{ found, sender_email, server_host, server_port, use_tls }` o `{ found: false }` |
| `POST` | `/api/v1/messages/profiles/{profile_id}/test-send` | Envia el correo de prueba contra el perfil ya guardado; requiere acceso al proyecto del perfil |

## Limites conocidos

- La tabla de proveedores conocidos es fija en codigo; agregar un proveedor
  nuevo requiere un cambio de codigo (no hay UI para administrarla).
- `send_test_email` usa un timeout de 15 segundos; servidores SMTP lentos
  pueden reportar fallo aunque el envio eventualmente hubiera funcionado.
