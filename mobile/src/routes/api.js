const express = require('express');
const router = express.Router();
const { authenticateToken, requireRole } = require('../middleware/auth');
const participantes = require('../controllers/participantesController');
const registros = require('../controllers/registrosController');
const plantillas = require('../controllers/plantillasController');
const estadisticas = require('../controllers/estadisticasController');

// ── Health check (no auth) ──
router.get('/health', (req, res) => {
  res.json({
    status: 'ok',
    version: '1.0.0',
    app: 'InfoMatt360 API',
    timestamp: new Date().toISOString(),
  });
});

// All other API routes require authentication
router.use(authenticateToken);

// ── Participantes ──
router.get('/participantes', participantes.list);
router.get('/participantes/:id', participantes.getById);
router.post('/participantes', participantes.create);
router.put('/participantes/:id', participantes.update);

// ── Plantillas (formularios) ──
router.get('/plantillas', plantillas.list);
router.get('/plantillas/:id', plantillas.getById);

// ── Registros ──
router.get('/registros', registros.list);
router.get('/registros/:id', registros.getById);
router.post('/registros', registros.create);
router.put('/registros/:id', registros.update);
router.delete('/registros/:id', requireRole('admin', 'supervisor'), registros.delete);

// ── Sincronización batch ──
router.post('/sync/batch', registros.syncBatch);

// ── Estadísticas ──
router.get('/estadisticas', requireRole('admin', 'supervisor'), estadisticas.resumen);
router.get('/estadisticas/exportar', requireRole('admin', 'supervisor'), estadisticas.exportar);

module.exports = router;
