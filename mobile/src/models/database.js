const Database = require('better-sqlite3');
const path = require('path');
require('dotenv').config();

const dbPath = path.resolve(process.env.DB_PATH || './data/infomatt360.db');
const db = new Database(dbPath);

// Enable WAL mode for better concurrent performance
db.pragma('journal_mode = WAL');
db.pragma('foreign_keys = ON');

function initDatabase() {
  db.exec(`
    -- ═══ ORGANIZACIONES ═══
    CREATE TABLE IF NOT EXISTS organizaciones (
      id TEXT PRIMARY KEY,
      nombre TEXT NOT NULL,
      nit TEXT UNIQUE,
      direccion TEXT,
      telefono TEXT,
      email TEXT,
      logo_url TEXT,
      activa INTEGER DEFAULT 1,
      created_at TEXT DEFAULT (datetime('now')),
      updated_at TEXT DEFAULT (datetime('now'))
    );

    -- ═══ USUARIOS ═══
    CREATE TABLE IF NOT EXISTS usuarios (
      id TEXT PRIMARY KEY,
      organizacion_id TEXT NOT NULL,
      nombre TEXT NOT NULL,
      email TEXT NOT NULL UNIQUE,
      password_hash TEXT NOT NULL,
      rol TEXT NOT NULL DEFAULT 'encuestador' CHECK(rol IN ('admin','supervisor','encuestador')),
      telefono TEXT,
      activo INTEGER DEFAULT 1,
      ultimo_login TEXT,
      created_at TEXT DEFAULT (datetime('now')),
      updated_at TEXT DEFAULT (datetime('now')),
      FOREIGN KEY (organizacion_id) REFERENCES organizaciones(id)
    );

    -- ═══ PROYECTOS ═══
    CREATE TABLE IF NOT EXISTS proyectos (
      id TEXT PRIMARY KEY,
      organizacion_id TEXT NOT NULL,
      nombre TEXT NOT NULL,
      descripcion TEXT,
      fecha_inicio TEXT,
      fecha_fin TEXT,
      estado TEXT DEFAULT 'activo' CHECK(estado IN ('activo','pausado','finalizado')),
      ubicacion_referencia TEXT,
      created_at TEXT DEFAULT (datetime('now')),
      updated_at TEXT DEFAULT (datetime('now')),
      FOREIGN KEY (organizacion_id) REFERENCES organizaciones(id)
    );

    -- ═══ ASIGNACIONES USUARIO-PROYECTO ═══
    CREATE TABLE IF NOT EXISTS usuario_proyecto (
      usuario_id TEXT NOT NULL,
      proyecto_id TEXT NOT NULL,
      rol_proyecto TEXT DEFAULT 'encuestador',
      assigned_at TEXT DEFAULT (datetime('now')),
      PRIMARY KEY (usuario_id, proyecto_id),
      FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
      FOREIGN KEY (proyecto_id) REFERENCES proyectos(id)
    );

    -- ═══ PLANTILLAS DE FORMULARIO ═══
    CREATE TABLE IF NOT EXISTS plantillas (
      id TEXT PRIMARY KEY,
      proyecto_id TEXT NOT NULL,
      nombre TEXT NOT NULL,
      descripcion TEXT,
      version INTEGER DEFAULT 1,
      campos_json TEXT NOT NULL, -- JSON schema de los campos
      activa INTEGER DEFAULT 1,
      orden INTEGER DEFAULT 0,
      created_at TEXT DEFAULT (datetime('now')),
      updated_at TEXT DEFAULT (datetime('now')),
      FOREIGN KEY (proyecto_id) REFERENCES proyectos(id)
    );

    -- ═══ PARTICIPANTES ═══
    CREATE TABLE IF NOT EXISTS participantes (
      id TEXT PRIMARY KEY,
      proyecto_id TEXT NOT NULL,
      codigo TEXT NOT NULL,
      nombre TEXT NOT NULL,
      tipo_documento TEXT NOT NULL CHECK(tipo_documento IN ('CC','TI','CE','PA','RC','NIT')),
      numero_documento TEXT NOT NULL,
      telefono TEXT,
      email TEXT,
      direccion TEXT,
      municipio TEXT,
      departamento TEXT,
      vereda TEXT,
      latitud REAL,
      longitud REAL,
      metadata_json TEXT, -- datos extra flexibles
      created_at TEXT DEFAULT (datetime('now')),
      updated_at TEXT DEFAULT (datetime('now')),
      FOREIGN KEY (proyecto_id) REFERENCES proyectos(id),
      UNIQUE(proyecto_id, numero_documento)
    );

    -- ═══ REGISTROS (respuestas de formularios) ═══
    CREATE TABLE IF NOT EXISTS registros (
      id TEXT PRIMARY KEY,
      plantilla_id TEXT NOT NULL,
      participante_id TEXT NOT NULL,
      usuario_id TEXT NOT NULL, -- quien capturó
      respuestas_json TEXT NOT NULL, -- JSON con las respuestas
      estado TEXT DEFAULT 'borrador' CHECK(estado IN ('borrador','completado','sincronizado','error')),
      latitud REAL,
      longitud REAL,
      precision_gps REAL,
      tiene_huella INTEGER DEFAULT 0,
      tiene_firma INTEGER DEFAULT 0,
      device_id TEXT,
      offline_id TEXT, -- ID generado offline para sincronización
      acta_generada INTEGER DEFAULT 0,
      acta_url TEXT,
      notas TEXT,
      created_at TEXT DEFAULT (datetime('now')),
      updated_at TEXT DEFAULT (datetime('now')),
      synced_at TEXT,
      FOREIGN KEY (plantilla_id) REFERENCES plantillas(id),
      FOREIGN KEY (participante_id) REFERENCES participantes(id),
      FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
    );

    -- ═══ EVIDENCIAS (fotos, archivos adjuntos) ═══
    CREATE TABLE IF NOT EXISTS evidencias (
      id TEXT PRIMARY KEY,
      registro_id TEXT NOT NULL,
      tipo TEXT NOT NULL CHECK(tipo IN ('foto','firma','huella','documento','audio','video')),
      nombre_archivo TEXT NOT NULL,
      ruta TEXT NOT NULL,
      mime_type TEXT,
      tamano_bytes INTEGER,
      metadata_json TEXT,
      created_at TEXT DEFAULT (datetime('now')),
      FOREIGN KEY (registro_id) REFERENCES registros(id) ON DELETE CASCADE
    );

    -- ═══ COLA DE SINCRONIZACIÓN ═══
    CREATE TABLE IF NOT EXISTS sync_queue (
      id TEXT PRIMARY KEY,
      tabla TEXT NOT NULL,
      registro_id TEXT NOT NULL,
      operacion TEXT NOT NULL CHECK(operacion IN ('INSERT','UPDATE','DELETE')),
      datos_json TEXT,
      intentos INTEGER DEFAULT 0,
      ultimo_error TEXT,
      estado TEXT DEFAULT 'pendiente' CHECK(estado IN ('pendiente','en_proceso','completado','error')),
      created_at TEXT DEFAULT (datetime('now')),
      processed_at TEXT
    );

    -- ═══ LOG DE ERRORES ═══
    CREATE TABLE IF NOT EXISTS error_logs (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      usuario_id TEXT,
      tipo TEXT NOT NULL,
      mensaje TEXT NOT NULL,
      stack_trace TEXT,
      device_info TEXT,
      created_at TEXT DEFAULT (datetime('now'))
    );

    -- ═══ SESIONES / REFRESH TOKENS ═══
    CREATE TABLE IF NOT EXISTS refresh_tokens (
      id TEXT PRIMARY KEY,
      usuario_id TEXT NOT NULL,
      token_hash TEXT NOT NULL,
      device_info TEXT,
      expires_at TEXT NOT NULL,
      created_at TEXT DEFAULT (datetime('now')),
      FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
    );

    -- ═══ ÍNDICES ═══
    CREATE INDEX IF NOT EXISTS idx_usuarios_email ON usuarios(email);
    CREATE INDEX IF NOT EXISTS idx_usuarios_org ON usuarios(organizacion_id);
    CREATE INDEX IF NOT EXISTS idx_participantes_proyecto ON participantes(proyecto_id);
    CREATE INDEX IF NOT EXISTS idx_participantes_doc ON participantes(numero_documento);
    CREATE INDEX IF NOT EXISTS idx_participantes_codigo ON participantes(codigo);
    CREATE INDEX IF NOT EXISTS idx_registros_plantilla ON registros(plantilla_id);
    CREATE INDEX IF NOT EXISTS idx_registros_participante ON registros(participante_id);
    CREATE INDEX IF NOT EXISTS idx_registros_usuario ON registros(usuario_id);
    CREATE INDEX IF NOT EXISTS idx_registros_estado ON registros(estado);
    CREATE INDEX IF NOT EXISTS idx_registros_fecha ON registros(created_at);
    CREATE INDEX IF NOT EXISTS idx_evidencias_registro ON evidencias(registro_id);
    CREATE INDEX IF NOT EXISTS idx_sync_queue_estado ON sync_queue(estado);
  `);

  console.log('✅ Base de datos inicializada correctamente');
}

module.exports = { db, initDatabase };
