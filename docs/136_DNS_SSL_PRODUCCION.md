# 136 — DNS y SSL para producción

> Pendiente operativo #3 de docs/96: documentar los pasos de configuración
> de dominio y certificado TLS para despliegue en producción.

---

## 1. Requisitos previos

| Elemento | Detalle |
|----------|---------|
| Dominio registrado | Ej. `app.infomatt360.com` |
| VPS/servidor con IP pública | La IP donde corren los servicios |
| Acceso al panel DNS del registrador | Namecheap, Cloudflare, GoDaddy, etc. |
| Puerto 80 y 443 abiertos en firewall | `ufw allow 80,443/tcp` |

---

## 2. Configurar registros DNS

### 2.1 Registro A (dominio raíz o subdominio)

```
Tipo:   A
Host:   app              (o @ para el dominio raíz)
Valor:  <IP_DEL_SERVIDOR>
TTL:    3600
```

### 2.2 Registro CNAME (opcional, alias `www`)

```
Tipo:   CNAME
Host:   www
Valor:  app.infomatt360.com
TTL:    3600
```

### 2.3 Verificar propagación

```bash
# Desde cualquier terminal
dig +short app.infomatt360.com A
# Debe devolver la IP del servidor

# O con nslookup
nslookup app.infomatt360.com
```

> La propagación DNS puede tardar de 5 minutos a 48 horas dependiendo del
> TTL previo y la caché del ISP. Usar `dig @8.8.8.8` fuerza la consulta
> contra los DNS de Google para verificar rápido.

---

## 3. Certificado SSL con Let's Encrypt (Certbot)

### 3.1 Instalar Certbot

```bash
# Ubuntu/Debian
sudo apt update && sudo apt install -y certbot

# Si se usa Nginx como reverse proxy:
sudo apt install -y python3-certbot-nginx
```

### 3.2 Obtener certificado (modo standalone)

Si **no hay** un reverse proxy corriendo en el puerto 80:

```bash
sudo certbot certonly --standalone \
  -d app.infomatt360.com \
  --email admin@infomatt360.com \
  --agree-tos --non-interactive
```

### 3.3 Obtener certificado (modo Nginx)

Si **Nginx está activo** como reverse proxy:

```bash
sudo certbot --nginx \
  -d app.infomatt360.com \
  --email admin@infomatt360.com \
  --agree-tos --non-interactive
```

### 3.4 Rutas de los certificados

```
/etc/letsencrypt/live/app.infomatt360.com/fullchain.pem   # Certificado + cadena
/etc/letsencrypt/live/app.infomatt360.com/privkey.pem      # Clave privada
```

### 3.5 Renovación automática

Certbot instala un timer de systemd o un cron que renueva automáticamente.
Verificar:

```bash
sudo certbot renew --dry-run
```

Si no hay timer, agregar cron:

```bash
echo "0 3 * * * root certbot renew --quiet --post-hook 'systemctl reload nginx'" \
  | sudo tee /etc/cron.d/certbot-renew
```

---

## 4. Configuración Nginx como reverse proxy

Archivo `/etc/nginx/sites-available/infomatt360`:

```nginx
# Redirigir HTTP → HTTPS
server {
    listen 80;
    server_name app.infomatt360.com;
    return 301 https://$host$request_uri;
}

# HTTPS — reverse proxy
server {
    listen 443 ssl http2;
    server_name app.infomatt360.com;

    ssl_certificate     /etc/letsencrypt/live/app.infomatt360.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/app.infomatt360.com/privkey.pem;

    # Seguridad TLS
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256';
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # Headers de seguridad
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains" always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-Frame-Options SAMEORIGIN always;

    # Límite de tamaño de carga (archivos/evidencias)
    client_max_body_size 50M;

    # Backend ERP (FastAPI) — API principal
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }

    # Backend móvil (Express) — API de campo
    location /mobile-api/ {
        rewrite ^/mobile-api/(.*) /api/v1/$1 break;
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Frontend React (SPA)
    location / {
        root /opt/infomatt360/frontend/dist;
        try_files $uri $uri/ /index.html;

        # Cache de assets estáticos
        location ~* \.(js|css|png|jpg|svg|ico|woff2?)$ {
            expires 30d;
            add_header Cache-Control "public, immutable";
        }
    }
}
```

Activar y recargar:

```bash
sudo ln -sf /etc/nginx/sites-available/infomatt360 /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

---

## 5. Variables de entorno para HTTPS

En el `.env` del backend ERP:

```env
# Dominio público (usado para CORS y cookies)
ALLOWED_ORIGINS=https://app.infomatt360.com
COOKIE_DOMAIN=app.infomatt360.com
COOKIE_SECURE=true

# Trusted proxies (Nginx)
FORWARDED_ALLOW_IPS=127.0.0.1
```

En el `.env` del frontend (build time):

```env
VITE_API_BASE_URL=https://app.infomatt360.com/api/v1
```

En el `.env` del backend móvil:

```env
CORS_ORIGIN=https://app.infomatt360.com
```

---

## 6. Verificación post-despliegue

```bash
# 1. Certificado válido
curl -vI https://app.infomatt360.com 2>&1 | grep "SSL certificate verify ok"

# 2. HSTS activo
curl -sI https://app.infomatt360.com | grep -i strict-transport

# 3. Redirect HTTP → HTTPS
curl -sI http://app.infomatt360.com | head -2
# Debe ser 301 → https://...

# 4. API responde
curl -s https://app.infomatt360.com/api/v1/health | jq .

# 5. Calificación SSL (navegador)
# Visitar: https://www.ssllabs.com/ssltest/analyze.html?d=app.infomatt360.com
```

---

## 7. Troubleshooting

| Síntoma | Causa probable | Solución |
|---------|---------------|----------|
| `ERR_NAME_NOT_RESOLVED` | DNS no propagado o registro mal configurado | Verificar con `dig @8.8.8.8`, esperar propagación |
| `ERR_CONNECTION_REFUSED` | Puertos 80/443 cerrados en firewall | `ufw allow 80,443/tcp` |
| `ERR_CERT_AUTHORITY_INVALID` | Certificado self-signed o cadena incompleta | Usar `fullchain.pem`, no `cert.pem` |
| Certbot falla con "Challenge failed" | Puerto 80 bloqueado o DNS apunta a otra IP | Verificar IP y abrir puerto 80 |
| Mixed Content warnings | Frontend carga recursos HTTP en página HTTPS | Asegurar que `VITE_API_BASE_URL` usa `https://` |
| `502 Bad Gateway` | Backend no está corriendo | `systemctl status infomatt360-api` |

---

## 8. Certificados para otros proveedores

Si no se usa Let's Encrypt (ej. certificado comercial de DigiCert, Comodo):

1. Generar CSR: `openssl req -new -newkey rsa:2048 -nodes -keyout server.key -out server.csr`
2. Enviar `server.csr` al proveedor y recibir el certificado `.crt`
3. Concatenar certificado + cadena intermedia: `cat server.crt intermediate.crt > fullchain.crt`
4. Configurar Nginx con `ssl_certificate fullchain.crt` y `ssl_certificate_key server.key`
