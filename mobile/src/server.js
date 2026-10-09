require('dotenv').config();
const express = require('express');
const cors = require('cors');
const path = require('path');
const { initDatabase } = require('./models/database');

const app = express();
const PORT = process.env.PORT || 3000;

// ── Initialize database ──
initDatabase();

// ── Middleware ──
app.use(cors({
  origin: process.env.CORS_ORIGIN || '*',
  methods: ['GET', 'POST', 'PUT', 'DELETE', 'PATCH'],
  allowedHeaders: ['Content-Type', 'Authorization'],
}));
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true }));

// ── Static files (uploads) ──
app.use('/uploads', express.static(path.join(__dirname, '..', 'uploads')));

// ── Serve frontend ──
app.use(express.static(path.join(__dirname, '..', 'public')));

// ── Health check (no auth) ──
app.get('/api/health', (req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString(), version: '1.0.0' });
});

// ── API docs summary (no auth required) ──
app.get('/api/v1', (req, res) => {
  res.json({
    app: 'InfoMatt360 API',
    version: '1.0.0',
    endpoints: {
      auth: {
        'POST /api/v1/auth/login': 'Iniciar sesión',
        'POST /api/v1/auth/refresh': 'Refrescar token',
        'GET  /api/v1/auth/me': 'Perfil del usuario actual',
        'POST /api/v1/auth/logout': 'Cerrar sesión',
      },
      participantes: {
        'GET    /api/v1/participantes': 'Listar participantes (search, page, limit)',
        'GET    /api/v1/participantes/:id': 'Detalle con estado de formularios',
        'POST   /api/v1/participantes': 'Crear participante',
        'PUT    /api/v1/participantes/:id': 'Actualizar participante',
      },
      plantillas: {
        'GET    /api/v1/plantillas': 'Listar plantillas de formulario',
        'GET    /api/v1/plantillas/:id': 'Detalle con esquema de campos',
      },
      registros: {
        'GET    /api/v1/registros': 'Listar registros (filtros: plantilla, participante, estado, fecha)',
        'GET    /api/v1/registros/:id': 'Detalle con respuestas y evidencias',
        'POST   /api/v1/registros': 'Crear registro',
        'PUT    /api/v1/registros/:id': 'Actualizar registro',
        'DELETE /api/v1/registros/:id': 'Eliminar borrador',
      },
      sync: {
        'POST   /api/v1/sync/batch': 'Sincronización batch de registros offline',
      },
      estadisticas: {
        'GET    /api/v1/estadisticas': 'Resumen con filtro de fechas',
        'GET    /api/v1/estadisticas/exportar': 'Exportar CSV o JSON',
      },
    },
  });
});

// ── API Routes ──
app.use('/api/v1/auth', require('./routes/auth'));
app.use('/api/v1', require('./routes/api'));

// ── 404 handler ──
app.use('/api', (req, res) => {
  res.status(404).json({ error: 'Endpoint no encontrado' });
});

// ── SPA fallback (Express 5 syntax) ──
app.get('/{*path}', (req, res) => {
  res.sendFile(path.join(__dirname, '..', 'public', 'index.html'));
});

// ── Error handler ──
app.use((err, req, res, next) => {
  console.error('Unhandled error:', err);
  res.status(500).json({ error: 'Error interno del servidor' });
});

// ── Start ──
if (require.main === module) {
  const server = app.listen(PORT, '0.0.0.0', () => {
    console.log(`
  ╔══════════════════════════════════════════╗
  ║     InfoMatt360 API v1.0.0              ║
  ║     Running on port ${PORT}                ║
  ║     http://localhost:${PORT}               ║
  ║     API: http://localhost:${PORT}/api/v1    ║
  ╚══════════════════════════════════════════╝
    `);
  });
  server.on('error', (err) => {
    console.error('Server error:', err.message);
    process.exit(1);
  });
}

module.exports = app;
