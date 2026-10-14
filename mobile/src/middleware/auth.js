const jwt = require('jsonwebtoken');
require('dotenv').config();

function authenticateToken(req, res, next) {
  const authHeader = req.headers['authorization'];
  const token = authHeader && authHeader.split(' ')[1]; // Bearer TOKEN

  if (!token) {
    return res.status(401).json({ error: req.t ? req.t('auth.tokenInvalid') : 'Token required' });
  }

  try {
    const decoded = jwt.verify(token, process.env.JWT_SECRET);
    req.user = decoded;
    next();
  } catch (err) {
    if (err.name === 'TokenExpiredError') {
      return res.status(401).json({ error: req.t ? req.t('auth.tokenInvalid') : 'Token expired', code: 'TOKEN_EXPIRED' });
    }
    return res.status(403).json({ error: req.t ? req.t('auth.tokenInvalid') : 'Invalid token' });
  }
}

function requireRole(...roles) {
  return (req, res, next) => {
    if (!req.user || !roles.includes(req.user.rol)) {
      return res.status(403).json({ error: req.t ? req.t('auth.accessDenied') : 'Access denied' });
    }
    next();
  };
}

module.exports = { authenticateToken, requireRole };
