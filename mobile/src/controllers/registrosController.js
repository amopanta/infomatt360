const { db } = require('../models/database');
const { v4: uuid } = require('uuid');

exports.list = (req, res) => {
  try {
    const { plantilla_id, participante_id, estado, desde, hasta, page = 1, limit = 50 } = req.query;
    const offset = (page - 1) * limit;
    let query = `SELECT r.*, pl.nombre as plantilla_nombre, pa.nombre as participante_nombre, pa.codigo as participante_codigo
      FROM registros r
      JOIN plantillas pl ON r.plantilla_id = pl.id
      JOIN participantes pa ON r.participante_id = pa.id
      WHERE r.usuario_id = ?`;
    const params = [req.user.id];

    if (plantilla_id) { query += ` AND r.plantilla_id = ?`; params.push(plantilla_id); }
    if (participante_id) { query += ` AND r.participante_id = ?`; params.push(participante_id); }
    if (estado) { query += ` AND r.estado = ?`; params.push(estado); }
    if (desde) { query += ` AND r.created_at >= ?`; params.push(desde); }
    if (hasta) { query += ` AND r.created_at <= ?`; params.push(hasta + 'T23:59:59'); }

    const countQ = query.replace(/SELECT[\s\S]*?FROM/, 'SELECT COUNT(*) as total FROM');
    const total = db.prepare(countQ).get(...params).total;

    query += ` ORDER BY r.created_at DESC LIMIT ? OFFSET ?`;
    params.push(Number(limit), Number(offset));

    const registros = db.prepare(query).all(...params);
    res.json({ data: registros, pagination: { page: Number(page), limit: Number(limit), total, pages: Math.ceil(total / limit) } });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Error al obtener registros' });
  }
};

exports.getById = (req, res) => {
  try {
    const registro = db.prepare(`
      SELECT r.*, pl.nombre as plantilla_nombre, pl.campos_json,
        pa.nombre as participante_nombre, pa.codigo as participante_codigo,
        pa.tipo_documento, pa.numero_documento
      FROM registros r
      JOIN plantillas pl ON r.plantilla_id = pl.id
      JOIN participantes pa ON r.participante_id = pa.id
      WHERE r.id = ?
    `).get(req.params.id);

    if (!registro) return res.status(404).json({ error: 'Registro no encontrado' });

    const evidencias = db.prepare('SELECT * FROM evidencias WHERE registro_id = ?').all(req.params.id);
    res.json({ ...registro, respuestas: JSON.parse(registro.respuestas_json), campos: JSON.parse(registro.campos_json), evidencias });
  } catch (err) {
    res.status(500).json({ error: 'Error al obtener registro' });
  }
};

exports.create = (req, res) => {
  try {
    const { plantilla_id, participante_id, respuestas, latitud, longitud, precision_gps, tiene_huella, tiene_firma, device_id, offline_id, notas } = req.body;

    if (!plantilla_id || !participante_id || !respuestas) {
      return res.status(400).json({ error: 'Campos requeridos: plantilla_id, participante_id, respuestas' });
    }

    // Check for duplicate offline_id
    if (offline_id) {
      const existing = db.prepare('SELECT id FROM registros WHERE offline_id = ?').get(offline_id);
      if (existing) return res.status(409).json({ error: 'Registro ya sincronizado', existing_id: existing.id });
    }

    const id = uuid();
    db.prepare(`INSERT INTO registros (id, plantilla_id, participante_id, usuario_id, respuestas_json, estado, latitud, longitud, precision_gps, tiene_huella, tiene_firma, device_id, offline_id, notas)
      VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)`).run(
      id, plantilla_id, participante_id, req.user.id,
      JSON.stringify(respuestas), 'completado',
      latitud || null, longitud || null, precision_gps || null,
      tiene_huella ? 1 : 0, tiene_firma ? 1 : 0,
      device_id || null, offline_id || null, notas || null
    );

    res.status(201).json(db.prepare('SELECT * FROM registros WHERE id = ?').get(id));
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Error al crear registro' });
  }
};

exports.update = (req, res) => {
  try {
    const existing = db.prepare('SELECT * FROM registros WHERE id = ?').get(req.params.id);
    if (!existing) return res.status(404).json({ error: 'Registro no encontrado' });

    const { respuestas, estado, notas, tiene_huella, tiene_firma } = req.body;

    db.prepare(`UPDATE registros SET
      respuestas_json = ?, estado = ?, notas = ?, tiene_huella = ?, tiene_firma = ?, updated_at = datetime('now')
      WHERE id = ?`).run(
      respuestas ? JSON.stringify(respuestas) : existing.respuestas_json,
      estado || existing.estado,
      notas ?? existing.notas,
      tiene_huella !== undefined ? (tiene_huella ? 1 : 0) : existing.tiene_huella,
      tiene_firma !== undefined ? (tiene_firma ? 1 : 0) : existing.tiene_firma,
      req.params.id
    );

    res.json(db.prepare('SELECT * FROM registros WHERE id = ?').get(req.params.id));
  } catch (err) {
    res.status(500).json({ error: 'Error al actualizar registro' });
  }
};

exports.delete = (req, res) => {
  try {
    const existing = db.prepare('SELECT * FROM registros WHERE id = ?').get(req.params.id);
    if (!existing) return res.status(404).json({ error: 'Registro no encontrado' });
    if (existing.estado === 'sincronizado') return res.status(400).json({ error: 'No se puede eliminar un registro ya sincronizado' });

    db.prepare('DELETE FROM registros WHERE id = ?').run(req.params.id);
    res.json({ success: true, message: 'Registro eliminado' });
  } catch (err) {
    res.status(500).json({ error: 'Error al eliminar registro' });
  }
};

// ── Sync batch ──
exports.syncBatch = (req, res) => {
  try {
    const { registros } = req.body;
    if (!Array.isArray(registros) || registros.length === 0) {
      return res.status(400).json({ error: 'Se requiere un array de registros' });
    }

    const results = { synced: [], errors: [] };

    const syncTransaction = db.transaction(() => {
      for (const reg of registros) {
        try {
          // Check duplicate
          if (reg.offline_id) {
            const exists = db.prepare('SELECT id FROM registros WHERE offline_id = ?').get(reg.offline_id);
            if (exists) { results.synced.push({ offline_id: reg.offline_id, id: exists.id, status: 'already_synced' }); continue; }
          }

          const id = uuid();
          db.prepare(`INSERT INTO registros (id, plantilla_id, participante_id, usuario_id, respuestas_json, estado, latitud, longitud, precision_gps, tiene_huella, tiene_firma, device_id, offline_id, created_at, synced_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'))`).run(
            id, reg.plantilla_id, reg.participante_id, req.user.id,
            JSON.stringify(reg.respuestas), 'sincronizado',
            reg.latitud, reg.longitud, reg.precision_gps,
            reg.tiene_huella ? 1 : 0, reg.tiene_firma ? 1 : 0,
            reg.device_id, reg.offline_id, reg.created_at
          );
          results.synced.push({ offline_id: reg.offline_id, id, status: 'synced' });
        } catch (err) {
          results.errors.push({ offline_id: reg.offline_id, error: err.message });
        }
      }
    });
    syncTransaction();

    res.json({ success: true, total: registros.length, synced: results.synced.length, errors: results.errors.length, details: results });
  } catch (err) {
    res.status(500).json({ error: 'Error en sincronización batch' });
  }
};
