const { db, initDatabase } = require('../models/database');
const bcrypt = require('bcryptjs');
const { v4: uuid } = require('uuid');

initDatabase();

console.log('🌱 Insertando datos de prueba...');

// ── Organización ──
const orgId = uuid();
db.prepare(`INSERT INTO organizaciones (id, nombre, nit, direccion, telefono, email) VALUES (?, ?, ?, ?, ?, ?)`).run(
  orgId, 'InfoMatt Colombia SAS', '900.123.456-7', 'Cra 7 #45-12, Bogotá', '601 234 5678', 'info@infomatt.co'
);

// ── Usuarios ──
const salt = bcrypt.genSaltSync(10);
const users = [
  { nombre: 'Carlos Martinez', email: 'carlos@infomatt.co', rol: 'encuestador', pass: 'Carlos123!' },
  { nombre: 'Laura Gómez', email: 'laura@infomatt.co', rol: 'supervisor', pass: 'Laura123!' },
  { nombre: 'Admin InfoMatt', email: 'admin@infomatt.co', rol: 'admin', pass: 'Admin123!' },
];
const userIds = [];
for (const u of users) {
  const id = uuid();
  userIds.push(id);
  db.prepare(`INSERT INTO usuarios (id, organizacion_id, nombre, email, password_hash, rol) VALUES (?,?,?,?,?,?)`).run(
    id, orgId, u.nombre, u.email, bcrypt.hashSync(u.pass, salt), u.rol
  );
}

// ── Proyecto ──
const projId = uuid();
db.prepare(`INSERT INTO proyectos (id, organizacion_id, nombre, descripcion, fecha_inicio, fecha_fin, ubicacion_referencia) VALUES (?,?,?,?,?,?,?)`).run(
  projId, orgId, 'Censo Rural Cundinamarca 2026', 'Levantamiento de información socioeconómica en zonas rurales de Cundinamarca',
  '2026-06-01', '2026-12-31', 'Cundinamarca, Colombia'
);

// Asignar usuarios al proyecto
for (const uid of userIds) {
  db.prepare(`INSERT INTO usuario_proyecto (usuario_id, proyecto_id) VALUES (?,?)`).run(uid, projId);
}

// ── Plantillas de formulario ──
const plantillas = [
  {
    nombre: 'Encuesta Socioeconómica',
    desc: 'Datos socioeconómicos del hogar',
    campos: [
      { id: 'nombre_completo', tipo: 'text', label: 'Nombre completo', requerido: true },
      { id: 'fecha_nacimiento', tipo: 'date', label: 'Fecha de nacimiento', requerido: true },
      { id: 'estado_civil', tipo: 'select', label: 'Estado civil', opciones: ['Soltero/a','Casado/a','Unión libre','Viudo/a','Divorciado/a'], requerido: true },
      { id: 'nivel_educativo', tipo: 'select', label: 'Nivel educativo', opciones: ['Ninguno','Primaria','Bachillerato','Técnico','Profesional','Posgrado'], requerido: true },
      { id: 'ocupacion', tipo: 'text', label: 'Ocupación principal', requerido: true },
      { id: 'ingreso_mensual', tipo: 'currency', label: 'Ingreso mensual (COP)', requerido: true },
      { id: 'personas_hogar', tipo: 'number', label: 'Personas en el hogar', requerido: true },
      { id: 'acceso_salud', tipo: 'radio', label: 'Acceso a salud', opciones: ['Sí — EPS Contributiva','Sí — EPS Subsidiada','No'], requerido: true },
      { id: 'huella', tipo: 'fingerprint', label: 'Huella dactilar', requerido: false },
      { id: 'firma', tipo: 'signature', label: 'Firma', requerido: true },
      { id: 'foto_vivienda', tipo: 'photo', label: 'Foto de vivienda', requerido: false },
      { id: 'observaciones', tipo: 'textarea', label: 'Observaciones', requerido: false },
    ]
  },
  {
    nombre: 'Ficha de Caracterización Familiar',
    desc: 'Información detallada de la familia',
    campos: [
      { id: 'jefe_hogar', tipo: 'text', label: 'Jefe del hogar', requerido: true },
      { id: 'tipo_vivienda', tipo: 'select', label: 'Tipo de vivienda', opciones: ['Casa rural','Apartamento','Finca','Habitación','Otro'], requerido: true },
      { id: 'material_paredes', tipo: 'select', label: 'Material paredes', opciones: ['Ladrillo','Adobe/Bahareque','Madera','Bloque','Otro'], requerido: true },
      { id: 'material_techo', tipo: 'select', label: 'Material techo', opciones: ['Teja de barro','Zinc','Eternit','Concreto','Otro'], requerido: true },
      { id: 'agua_potable', tipo: 'radio', label: 'Agua potable', opciones: ['Sí — acueducto','Sí — pozo','No'], requerido: true },
      { id: 'energia', tipo: 'radio', label: 'Energía eléctrica', opciones: ['Sí — interconectado','Sí — solar','No'], requerido: true },
      { id: 'internet', tipo: 'radio', label: 'Internet', opciones: ['Sí','No'], requerido: true },
      { id: 'observaciones', tipo: 'textarea', label: 'Observaciones', requerido: false },
    ]
  },
  {
    nombre: 'Registro de Cultivos y Producción',
    desc: 'Cultivos, áreas y producción',
    campos: [
      { id: 'cultivo_principal', tipo: 'text', label: 'Cultivo principal', requerido: true },
      { id: 'area_hectareas', tipo: 'number', label: 'Área (hectáreas)', requerido: true },
      { id: 'produccion_ton', tipo: 'number', label: 'Producción (toneladas/año)', requerido: true },
      { id: 'destino', tipo: 'select', label: 'Destino de producción', opciones: ['Autoconsumo','Venta local','Venta mayorista','Exportación','Mixto'], requerido: true },
      { id: 'asistencia_tecnica', tipo: 'radio', label: 'Recibe asistencia técnica', opciones: ['Sí','No'], requerido: true },
      { id: 'acceso_credito', tipo: 'radio', label: 'Acceso a crédito agrario', opciones: ['Sí','No'], requerido: true },
      { id: 'foto_cultivo', tipo: 'photo', label: 'Foto del cultivo', requerido: false },
      { id: 'observaciones', tipo: 'textarea', label: 'Observaciones', requerido: false },
    ]
  },
  {
    nombre: 'Evaluación de Vivienda Rural',
    desc: 'Estado de la vivienda',
    campos: [
      { id: 'estado_general', tipo: 'select', label: 'Estado general', opciones: ['Bueno','Regular','Malo','En riesgo'], requerido: true },
      { id: 'num_habitaciones', tipo: 'number', label: 'Número de habitaciones', requerido: true },
      { id: 'bano', tipo: 'radio', label: 'Tiene baño', opciones: ['Sí — dentro','Sí — fuera','No'], requerido: true },
      { id: 'cocina', tipo: 'select', label: 'Tipo de cocina', opciones: ['Gas natural','Gas propano','Leña','Eléctrica','No tiene'], requerido: true },
      { id: 'riesgo_inundacion', tipo: 'radio', label: 'Riesgo de inundación', opciones: ['Alto','Medio','Bajo','Ninguno'], requerido: true },
      { id: 'riesgo_deslizamiento', tipo: 'radio', label: 'Riesgo de deslizamiento', opciones: ['Alto','Medio','Bajo','Ninguno'], requerido: true },
      { id: 'fotos', tipo: 'photo_multiple', label: 'Fotos de la vivienda', requerido: true },
      { id: 'observaciones', tipo: 'textarea', label: 'Observaciones', requerido: false },
    ]
  },
];

const plantillaIds = [];
for (let i = 0; i < plantillas.length; i++) {
  const p = plantillas[i];
  const id = uuid();
  plantillaIds.push(id);
  db.prepare(`INSERT INTO plantillas (id, proyecto_id, nombre, descripcion, campos_json, orden) VALUES (?,?,?,?,?,?)`).run(
    id, projId, p.nombre, p.desc, JSON.stringify(p.campos), i
  );
}

// ── Participantes ──
const participantesData = [
  { nombre: 'María Elena Rodríguez Gómez', tipoDoc: 'CC', numDoc: '52489731', codigo: 'P-0001', tel: '310 456 7890', mun: 'Choachí', dep: 'Cundinamarca', vereda: 'El Rosario' },
  { nombre: 'Juan Carlos Pérez Martínez', tipoDoc: 'CC', numDoc: '1032876543', codigo: 'P-0002', tel: '311 234 5678', mun: 'La Calera', dep: 'Cundinamarca', vereda: 'San José' },
  { nombre: 'Ana Sofía Hernández López', tipoDoc: 'CC', numDoc: '39852147', codigo: 'P-0003', tel: '315 678 9012', mun: 'Ubaque', dep: 'Cundinamarca', vereda: 'Centro' },
  { nombre: 'Pedro Antonio Morales Díaz', tipoDoc: 'CC', numDoc: '79456123', codigo: 'P-0004', tel: '320 111 2233', mun: 'Fómeque', dep: 'Cundinamarca', vereda: 'La Unión' },
  { nombre: 'Luz Marina Castro Vargas', tipoDoc: 'TI', numDoc: '1098765432', codigo: 'P-0005', tel: null, mun: 'Choachí', dep: 'Cundinamarca', vereda: 'Ferralarada' },
  { nombre: 'Diego Fernando Ruiz Acosta', tipoDoc: 'CC', numDoc: '80321654', codigo: 'P-0006', tel: '300 987 6543', mun: 'La Calera', dep: 'Cundinamarca', vereda: 'El Salitre' },
];

const participanteIds = [];
for (const p of participantesData) {
  const id = uuid();
  participanteIds.push(id);
  const lat = 4.7110 + (Math.random() - 0.5) * 0.05;
  const lng = -74.0721 + (Math.random() - 0.5) * 0.05;
  db.prepare(`INSERT INTO participantes (id, proyecto_id, codigo, nombre, tipo_documento, numero_documento, telefono, municipio, departamento, vereda, latitud, longitud) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)`).run(
    id, projId, p.codigo, p.nombre, p.tipoDoc, p.numDoc, p.tel, p.mun, p.dep, p.vereda, lat, lng
  );
}

// ── Registros (simulados) ──
const estados = ['sincronizado', 'sincronizado', 'sincronizado', 'sincronizado', 'completado', 'borrador'];
const insertReg = db.prepare(`INSERT INTO registros (id, plantilla_id, participante_id, usuario_id, respuestas_json, estado, latitud, longitud, tiene_huella, tiene_firma, created_at, synced_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)`);

const baseDate = new Date('2026-06-01');
const today = new Date('2026-10-07');
let regCount = 0;

const insertMany = db.transaction(() => {
  for (let d = new Date(baseDate); d <= today; d.setDate(d.getDate() + 1)) {
    const dow = d.getDay();
    const count = dow === 0 ? 2 : dow === 6 ? 3 : Math.floor(Math.random() * 4) + 2;
    for (let i = 0; i < count; i++) {
      const hour = 6 + Math.floor(Math.random() * 12);
      const plantIdx = Math.floor(Math.random() * plantillaIds.length);
      const partIdx = Math.floor(Math.random() * participanteIds.length);
      const estado = estados[Math.floor(Math.random() * estados.length)];
      const lat = 4.7110 + (Math.random() - 0.5) * 0.03;
      const lng = -74.0721 + (Math.random() - 0.5) * 0.03;
      const createdAt = new Date(d.getFullYear(), d.getMonth(), d.getDate(), hour, Math.floor(Math.random() * 60));

      insertReg.run(
        uuid(),
        plantillaIds[plantIdx],
        participanteIds[partIdx],
        userIds[0], // Carlos
        JSON.stringify({ _auto: true, _sample: 'datos de ejemplo' }),
        estado,
        lat, lng,
        Math.random() > 0.3 ? 1 : 0,
        Math.random() > 0.2 ? 1 : 0,
        createdAt.toISOString(),
        estado === 'sincronizado' ? new Date(createdAt.getTime() + 3600000).toISOString() : null
      );
      regCount++;
    }
  }
});
insertMany();

console.log(`✅ Seed completado:
   • 1 organización
   • ${users.length} usuarios
   • 1 proyecto
   • ${plantillas.length} plantillas de formulario
   • ${participantesData.length} participantes
   • ${regCount} registros simulados
`);

console.log(`
🔑 Credenciales de prueba:
   Encuestador: carlos@infomatt.co / Carlos123!
   Supervisor:  laura@infomatt.co  / Laura123!
   Admin:       admin@infomatt.co  / Admin123!
`);
