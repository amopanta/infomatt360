const { db } = require('../models/database');
const { v4: uuid } = require('uuid');

function mapTerritory(row) {
  if (!row) return null;
  return {
    id: row.id,
    user_id: row.user_id,
    department: row.departamento,
    municipality: row.municipio,
    created_at: row.created_at,
  };
}

// GET /territories/:projectId — list territories for a project
exports.list = (req, res) => {
  try {
    const rows = db.prepare(`
      SELECT ut.*, u.nombre as user_name
      FROM user_territories ut
      JOIN usuarios u ON u.id = ut.user_id
      WHERE ut.proyecto_id = ?
      ORDER BY ut.departamento, ut.municipio
    `).all(req.params.projectId);

    res.json(rows.map(r => ({ ...mapTerritory(r), user_name: r.user_name })));
  } catch (err) {
    console.error('Error listing territories:', err);
    res.status(500).json({ error: 'Error al listar territorios' });
  }
};

// POST /territories/:projectId — assign territory
exports.assign = (req, res) => {
  try {
    const { user_id, department, municipality } = req.body;
    if (!user_id || !department || !municipality) {
      return res.status(400).json({ error: 'Campos requeridos: user_id, department, municipality' });
    }

    // Verify user belongs to project
    const membership = db.prepare(`
      SELECT 1 FROM usuario_proyecto WHERE usuario_id = ? AND proyecto_id = ?
    `).get(user_id, req.params.projectId);
    if (!membership) {
      return res.status(400).json({ error: 'El usuario no pertenece a este proyecto' });
    }

    const id = uuid();
    db.prepare(`
      INSERT INTO user_territories (id, proyecto_id, user_id, departamento, municipio)
      VALUES (?, ?, ?, ?, ?)
    `).run(id, req.params.projectId, user_id, department, municipality);

    const created = db.prepare('SELECT * FROM user_territories WHERE id = ?').get(id);
    res.status(201).json(mapTerritory(created));
  } catch (err) {
    if (err.message?.includes('UNIQUE')) {
      return res.status(409).json({ error: 'Este territorio ya está asignado a este usuario' });
    }
    console.error('Error assigning territory:', err);
    res.status(500).json({ error: 'Error al asignar territorio' });
  }
};

// DELETE /territories/:projectId/:id — remove territory
exports.remove = (req, res) => {
  try {
    const territory = db.prepare('SELECT * FROM user_territories WHERE id = ? AND proyecto_id = ?')
      .get(req.params.id, req.params.projectId);
    if (!territory) return res.status(404).json({ error: 'Territorio no encontrado' });

    db.prepare('DELETE FROM user_territories WHERE id = ?').run(req.params.id);
    res.json({ message: 'Territorio eliminado', id: req.params.id });
  } catch (err) {
    console.error('Error removing territory:', err);
    res.status(500).json({ error: 'Error al eliminar territorio' });
  }
};
