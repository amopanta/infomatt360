const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const { v4: uuid } = require('uuid');
const { db } = require('../models/database');
require('dotenv').config();

function generateTokens(user) {
  const accessToken = jwt.sign(
    { id: user.id, email: user.email, rol: user.rol, organizacion_id: user.organizacion_id },
    process.env.JWT_SECRET,
    { expiresIn: process.env.JWT_EXPIRES_IN || '24h' }
  );
  const refreshToken = jwt.sign(
    { id: user.id, type: 'refresh' },
    process.env.JWT_REFRESH_SECRET,
    { expiresIn: process.env.JWT_REFRESH_EXPIRES_IN || '7d' }
  );
  return { accessToken, refreshToken };
}

exports.login = (req, res) => {
  try {
    const { email, password, organizacion } = req.body;

    if (!email || !password) {
      return res.status(400).json({ error: 'Email y contraseña son requeridos' });
    }

    // Find user with org info
    const user = db.prepare(`
      SELECT u.*, o.nombre as organizacion_nombre
      FROM usuarios u
      JOIN organizaciones o ON u.organizacion_id = o.id
      WHERE u.email = ? AND u.activo = 1
    `).get(email.toLowerCase().trim());

    if (!user) {
      return res.status(401).json({ error: 'Credenciales inválidas' });
    }

    const validPassword = bcrypt.compareSync(password, user.password_hash);
    if (!validPassword) {
      return res.status(401).json({ error: 'Credenciales inválidas' });
    }

    // Get active project
    const proyecto = db.prepare(`
      SELECT p.* FROM proyectos p
      JOIN usuario_proyecto up ON p.id = up.proyecto_id
      WHERE up.usuario_id = ? AND p.estado = 'activo'
      ORDER BY p.created_at DESC LIMIT 1
    `).get(user.id);

    // Update last login
    db.prepare(`UPDATE usuarios SET ultimo_login = datetime('now') WHERE id = ?`).run(user.id);

    const tokens = generateTokens(user);

    // Store refresh token
    const expiresAt = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString();
    db.prepare(`INSERT INTO refresh_tokens (id, usuario_id, token_hash, expires_at) VALUES (?,?,?,?)`).run(
      uuid(), user.id, bcrypt.hashSync(tokens.refreshToken, 8), expiresAt
    );

    res.json({
      success: true,
      user: {
        id: user.id,
        nombre: user.nombre,
        email: user.email,
        rol: user.rol,
        organizacion: {
          id: user.organizacion_id,
          nombre: user.organizacion_nombre,
        },
        proyecto_activo: proyecto ? {
          id: proyecto.id,
          nombre: proyecto.nombre,
          descripcion: proyecto.descripcion,
        } : null,
      },
      tokens,
    });
  } catch (err) {
    console.error('Login error:', err);
    res.status(500).json({ error: 'Error interno del servidor' });
  }
};

exports.refreshToken = (req, res) => {
  try {
    const { refreshToken } = req.body;
    if (!refreshToken) {
      return res.status(400).json({ error: 'Refresh token requerido' });
    }

    const decoded = jwt.verify(refreshToken, process.env.JWT_REFRESH_SECRET);
    const user = db.prepare(`
      SELECT u.*, o.nombre as organizacion_nombre
      FROM usuarios u JOIN organizaciones o ON u.organizacion_id = o.id
      WHERE u.id = ? AND u.activo = 1
    `).get(decoded.id);

    if (!user) {
      return res.status(401).json({ error: 'Usuario no encontrado' });
    }

    // Clean old refresh tokens
    db.prepare(`DELETE FROM refresh_tokens WHERE usuario_id = ? AND expires_at < datetime('now')`).run(user.id);

    const tokens = generateTokens(user);
    res.json({ success: true, tokens });
  } catch (err) {
    res.status(401).json({ error: 'Refresh token inválido o expirado' });
  }
};

exports.me = (req, res) => {
  try {
    const user = db.prepare(`
      SELECT u.id, u.nombre, u.email, u.rol, u.telefono, u.ultimo_login,
             o.id as org_id, o.nombre as org_nombre
      FROM usuarios u JOIN organizaciones o ON u.organizacion_id = o.id
      WHERE u.id = ?
    `).get(req.user.id);

    if (!user) return res.status(404).json({ error: 'Usuario no encontrado' });

    const proyecto = db.prepare(`
      SELECT p.* FROM proyectos p
      JOIN usuario_proyecto up ON p.id = up.proyecto_id
      WHERE up.usuario_id = ? AND p.estado = 'activo' LIMIT 1
    `).get(user.id);

    const stats = db.prepare(`
      SELECT COUNT(*) as total,
        SUM(CASE WHEN estado = 'sincronizado' THEN 1 ELSE 0 END) as sincronizados
      FROM registros WHERE usuario_id = ?
    `).get(user.id);

    res.json({
      ...user,
      organizacion: { id: user.org_id, nombre: user.org_nombre },
      proyecto_activo: proyecto,
      estadisticas: stats,
    });
  } catch (err) {
    res.status(500).json({ error: 'Error interno' });
  }
};

exports.logout = (req, res) => {
  db.prepare(`DELETE FROM refresh_tokens WHERE usuario_id = ?`).run(req.user.id);
  res.json({ success: true, message: 'Sesión cerrada' });
};
