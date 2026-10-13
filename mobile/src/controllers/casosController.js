const { db } = require('../models/database');
const { v4: uuid } = require('uuid');

/**
 * Map DB row (Spanish columns) → API response (English, matching ERP frontend contract)
 */
function mapCase(row) {
  if (!row) return null;
  return {
    id: row.id,
    participant_id: row.participante_id,
    title: row.titulo,
    status: row.estado,
    assigned_user_id: row.assigned_user_id,
    due_at: row.due_at,
    properties: JSON.parse(row.propiedades_json || '{}'),
    created_by: row.created_by,
    created_at: row.created_at,
    updated_at: row.updated_at,
  };
}

function mapEvent(row) {
  if (!row) return null;
  return {
    id: row.id,
    case_id: row.caso_id,
    event_type: row.event_type,
    note: row.nota,
    from_user_id: row.from_user_id,
    to_user_id: row.to_user_id,
    created_at: row.created_at,
  };
}

// GET /cases/participant/:participantId — list cases for a participant
exports.listByParticipant = (req, res) => {
  try {
    const rows = db.prepare(`
      SELECT * FROM casos WHERE participante_id = ? ORDER BY created_at DESC
    `).all(req.params.participantId);
    res.json(rows.map(mapCase));
  } catch (err) {
    console.error('Error listing cases:', err);
    res.status(500).json({ error: 'Error al listar casos' });
  }
};

// GET /cases/:id — get single case
exports.getById = (req, res) => {
  try {
    const row = db.prepare('SELECT * FROM casos WHERE id = ?').get(req.params.id);
    if (!row) return res.status(404).json({ error: 'Caso no encontrado' });
    res.json(mapCase(row));
  } catch (err) {
    res.status(500).json({ error: 'Error al obtener caso' });
  }
};

// POST /cases — create a case
exports.create = (req, res) => {
  try {
    const { participant_id, title, assigned_user_id, due_at, properties, reminder_channels } = req.body;
    if (!participant_id || !title) {
      return res.status(400).json({ error: 'Campos requeridos: participant_id, title' });
    }

    // Verify participant exists
    const part = db.prepare('SELECT id FROM participantes WHERE id = ?').get(participant_id);
    if (!part) return res.status(404).json({ error: 'Participante no encontrado' });

    const id = uuid();
    const userId = req.user.id;

    db.prepare(`
      INSERT INTO casos (id, participante_id, titulo, assigned_user_id, due_at, propiedades_json, created_by)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    `).run(id, participant_id, title, assigned_user_id || null, due_at || null, JSON.stringify(properties || {}), userId);

    // Create initial event
    db.prepare(`
      INSERT INTO caso_eventos (id, caso_id, event_type, nota, from_user_id, to_user_id)
      VALUES (?, ?, 'created', ?, ?, ?)
    `).run(uuid(), id, `Caso creado: ${title}`, userId, assigned_user_id || null);

    const created = db.prepare('SELECT * FROM casos WHERE id = ?').get(id);
    res.status(201).json(mapCase(created));
  } catch (err) {
    console.error('Error creating case:', err);
    res.status(500).json({ error: 'Error al crear caso' });
  }
};

// PATCH /cases/:id — update case (status, assignment, due_at, note)
exports.update = (req, res) => {
  try {
    const existing = db.prepare('SELECT * FROM casos WHERE id = ?').get(req.params.id);
    if (!existing) return res.status(404).json({ error: 'Caso no encontrado' });

    const { status, assigned_user_id, due_at, note } = req.body;
    const userId = req.user.id;
    const events = [];

    // Track status change
    if (status && status !== existing.estado) {
      events.push({ type: 'status_change', note: `Estado: ${existing.estado} → ${status}`, to: null });
    }

    // Track assignment change (only when key is explicitly in body)
    const hasAssignment = 'assigned_user_id' in req.body;
    if (hasAssignment && req.body.assigned_user_id !== existing.assigned_user_id) {
      events.push({ type: 'assigned', note: `Reasignado`, to: req.body.assigned_user_id });
    }

    // Add note event
    if (note) {
      events.push({ type: 'note', note, to: null });
    }

    const newAssigned = hasAssignment ? req.body.assigned_user_id : existing.assigned_user_id;
    const newDue = 'due_at' in req.body ? req.body.due_at : existing.due_at;

    db.prepare(`
      UPDATE casos SET
        estado = ?,
        assigned_user_id = ?,
        due_at = ?,
        updated_at = datetime('now')
      WHERE id = ?
    `).run(
      status || existing.estado,
      newAssigned,
      newDue,
      req.params.id
    );

    // Insert events
    const insertEvent = db.prepare(`
      INSERT INTO caso_eventos (id, caso_id, event_type, nota, from_user_id, to_user_id)
      VALUES (?, ?, ?, ?, ?, ?)
    `);
    for (const ev of events) {
      insertEvent.run(uuid(), req.params.id, ev.type, ev.note, userId, ev.to);
    }

    const updated = db.prepare('SELECT * FROM casos WHERE id = ?').get(req.params.id);
    res.json(mapCase(updated));
  } catch (err) {
    console.error('Error updating case:', err);
    res.status(500).json({ error: 'Error al actualizar caso' });
  }
};

// GET /cases/:id/events — list case timeline
exports.listEvents = (req, res) => {
  try {
    const caso = db.prepare('SELECT id FROM casos WHERE id = ?').get(req.params.id);
    if (!caso) return res.status(404).json({ error: 'Caso no encontrado' });

    const rows = db.prepare(`
      SELECT * FROM caso_eventos WHERE caso_id = ? ORDER BY created_at ASC
    `).all(req.params.id);
    res.json(rows.map(mapEvent));
  } catch (err) {
    res.status(500).json({ error: 'Error al listar eventos' });
  }
};

// GET /cases/project/:projectId/assignees — list users assignable in project
exports.listAssignees = (req, res) => {
  try {
    const users = db.prepare(`
      SELECT u.id, u.nombre as full_name
      FROM usuarios u
      JOIN usuario_proyecto up ON up.usuario_id = u.id
      WHERE up.proyecto_id = ? AND u.activo = 1
      ORDER BY u.nombre
    `).all(req.params.projectId);
    res.json(users);
  } catch (err) {
    res.status(500).json({ error: 'Error al listar asignables' });
  }
};
