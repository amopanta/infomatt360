const { db } = require('../models/database');

exports.list = (req, res) => {
  try {
    const { proyecto_id } = req.query;
    let query = `SELECT pl.*,
      (SELECT COUNT(*) FROM registros r WHERE r.plantilla_id = pl.id) as total_registros
      FROM plantillas pl WHERE pl.activa = 1`;
    const params = [];

    if (proyecto_id) { query += ` AND pl.proyecto_id = ?`; params.push(proyecto_id); }
    query += ` ORDER BY pl.orden`;

    const plantillas = db.prepare(query).all(...params);
    res.json({ data: plantillas.map(p => ({ ...p, campos: JSON.parse(p.campos_json) })) });
  } catch (err) {
    res.status(500).json({ error: 'Error al obtener plantillas' });
  }
};

exports.getById = (req, res) => {
  try {
    const plantilla = db.prepare('SELECT * FROM plantillas WHERE id = ?').get(req.params.id);
    if (!plantilla) return res.status(404).json({ error: 'Plantilla no encontrada' });
    res.json({ ...plantilla, campos: JSON.parse(plantilla.campos_json) });
  } catch (err) {
    res.status(500).json({ error: 'Error al obtener plantilla' });
  }
};
