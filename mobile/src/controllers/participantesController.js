const { db } = require('../models/database');
const { v4: uuid } = require('uuid');

exports.list = (req, res) => {
  try {
    const { search, page = 1, limit = 50, proyecto_id } = req.query;
    const offset = (page - 1) * limit;

    let query = `SELECT p.*,
      (SELECT COUNT(*) FROM registros r WHERE r.participante_id = p.id) as total_registros,
      (SELECT COUNT(*) FROM registros r WHERE r.participante_id = p.id AND r.estado = 'sincronizado') as registros_sincronizados
      FROM participantes p WHERE 1=1`;
    const params = [];

    if (proyecto_id) {
      query += ` AND p.proyecto_id = ?`;
      params.push(proyecto_id);
    }

    if (search) {
      query += ` AND (p.nombre LIKE ? OR p.numero_documento LIKE ? OR p.codigo LIKE ?)`;
      const s = `%${search}%`;
      params.push(s, s, s);
    }

    const countQuery = query.replace(/SELECT[\s\S]*?FROM participantes/, 'SELECT COUNT(*) as total FROM participantes');
    const total = db.prepare(countQuery).get(...params).total;

    query += ` ORDER BY p.nombre ASC LIMIT ? OFFSET ?`;
    params.push(Number(limit), Number(offset));

    const participantes = db.prepare(query).all(...params);

    res.json({
      data: participantes,
      pagination: { page: Number(page), limit: Number(limit), total, pages: Math.ceil(total / limit) },
    });
  } catch (err) {
    console.error('Error listing participantes:', err);
    res.status(500).json({ error: 'Error al obtener participantes' });
  }
};

exports.getById = (req, res) => {
  try {
    const participante = db.prepare(`SELECT * FROM participantes WHERE id = ?`).get(req.params.id);
    if (!participante) return res.status(404).json({ error: 'Participante no encontrado' });

    // Get form statuses
    const registros = db.prepare(`
      SELECT r.*, pl.nombre as plantilla_nombre
      FROM registros r
      JOIN plantillas pl ON r.plantilla_id = pl.id
      WHERE r.participante_id = ?
      ORDER BY r.created_at DESC
    `).all(req.params.id);

    // Get available templates for this project
    const plantillas = db.prepare(`
      SELECT pl.* FROM plantillas pl
      WHERE pl.proyecto_id = ? AND pl.activa = 1
      ORDER BY pl.orden
    `).all(participante.proyecto_id);

    const formStatus = plantillas.map(pl => {
      const registro = registros.find(r => r.plantilla_id === pl.id);
      return {
        plantilla_id: pl.id,
        plantilla_nombre: pl.nombre,
        aplicado: !!registro,
        registro: registro || null,
      };
    });

    res.json({ ...participante, formStatus, registros });
  } catch (err) {
    res.status(500).json({ error: 'Error al obtener participante' });
  }
};

exports.create = (req, res) => {
  try {
    const { proyecto_id, nombre, tipo_documento, numero_documento, codigo, telefono, email, direccion, municipio, departamento, vereda, latitud, longitud } = req.body;

    if (!proyecto_id || !nombre || !tipo_documento || !numero_documento) {
      return res.status(400).json({ error: 'Campos requeridos: proyecto_id, nombre, tipo_documento, numero_documento' });
    }

    const id = uuid();
    const autoCode = codigo || `P-${String(db.prepare('SELECT COUNT(*)+1 as n FROM participantes WHERE proyecto_id=?').get(proyecto_id).n).padStart(4,'0')}`;

    db.prepare(`INSERT INTO participantes (id, proyecto_id, codigo, nombre, tipo_documento, numero_documento, telefono, email, direccion, municipio, departamento, vereda, latitud, longitud)
      VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)`).run(
      id, proyecto_id, autoCode, nombre, tipo_documento, numero_documento, telefono || null, email || null, direccion || null, municipio || null, departamento || null, vereda || null, latitud || null, longitud || null
    );

    const created = db.prepare('SELECT * FROM participantes WHERE id = ?').get(id);
    res.status(201).json(created);
  } catch (err) {
    if (err.message?.includes('UNIQUE')) {
      return res.status(409).json({ error: 'Ya existe un participante con ese documento en este proyecto' });
    }
    res.status(500).json({ error: 'Error al crear participante' });
  }
};

exports.update = (req, res) => {
  try {
    const { nombre, telefono, email, direccion, municipio, departamento, vereda, latitud, longitud } = req.body;
    const existing = db.prepare('SELECT * FROM participantes WHERE id = ?').get(req.params.id);
    if (!existing) return res.status(404).json({ error: 'Participante no encontrado' });

    db.prepare(`UPDATE participantes SET nombre=?, telefono=?, email=?, direccion=?, municipio=?, departamento=?, vereda=?, latitud=?, longitud=?, updated_at=datetime('now') WHERE id=?`).run(
      nombre || existing.nombre, telefono ?? existing.telefono, email ?? existing.email,
      direccion ?? existing.direccion, municipio ?? existing.municipio, departamento ?? existing.departamento,
      vereda ?? existing.vereda, latitud ?? existing.latitud, longitud ?? existing.longitud, req.params.id
    );

    res.json(db.prepare('SELECT * FROM participantes WHERE id = ?').get(req.params.id));
  } catch (err) {
    res.status(500).json({ error: 'Error al actualizar participante' });
  }
};
