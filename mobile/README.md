# InfoMatt360 Mobile

Modulo movil de InfoMatt360 para recoleccion de datos en campo. Aplicacion
ligera (Node.js + Express 5 + SQLite) con SPA optimizada para dispositivos
moviles, sincronizacion offline y captura de GPS, huellas y firmas.

## Arquitectura

```
mobile/
  public/          # SPA frontend (index.html + assets)
    img/           # Logo SVG y favicon
  src/
    server.js      # Express 5 con SPA fallback
    controllers/   # Auth, registros, participantes, plantillas, estadisticas
    models/        # SQLite con better-sqlite3
    middleware/     # JWT auth
    routes/        # API v1 routes
    utils/         # Seed data
  Dockerfile       # Imagen Docker para produccion
```

## Arranque rapido

```bash
cp .env.example .env
npm install
npm run seed    # Datos de prueba
npm start       # http://localhost:3000
```

## Credenciales demo

| Usuario              | Clave       | Rol          |
|----------------------|-------------|--------------|
| carlos@infomatt.co   | Carlos123!  | Encuestador  |
| laura@infomatt.co    | Laura123!   | Supervisor   |
| admin@infomatt.co    | Admin123!   | Admin        |

## API Endpoints

- `GET  /api/health` - Health check
- `POST /api/v1/auth/login` - Iniciar sesion
- `POST /api/v1/auth/refresh` - Refrescar token
- `GET  /api/v1/auth/me` - Perfil actual
- `GET  /api/v1/participantes` - Listar participantes
- `GET  /api/v1/plantillas` - Listar formularios
- `GET  /api/v1/registros` - Listar registros (filtros: estado, fecha, plantilla)
- `POST /api/v1/registros` - Crear registro
- `POST /api/v1/sync/batch` - Sincronizacion batch offline
- `GET  /api/v1/estadisticas` - Dashboard con metricas
- `GET  /api/v1/estadisticas/exportar` - Exportar CSV/JSON

## Docker

```bash
docker build -t infomatt360-mobile .
docker run -p 3000:3000 \
  -e JWT_SECRET=tu_secreto_seguro_aqui \
  -e JWT_REFRESH_SECRET=otro_secreto_seguro \
  -v ./data:/app/data \
  infomatt360-mobile
```

## Caracteristicas

- SPA movil responsiva con modo claro/oscuro
- Autenticacion JWT con refresh token
- Captura de formularios dinamicos
- GPS, huella dactilar y firma digital
- Sincronizacion batch offline con deteccion de duplicados
- Estadisticas con graficas interactivas
- Exportacion CSV y JSON
- Mapa de registros con pines por estado
- Paleta de marca InfoMatt (#0A2540, #0066CC, #00C2FF)
