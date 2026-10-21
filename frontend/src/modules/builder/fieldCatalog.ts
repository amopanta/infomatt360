import type { BuilderPaletteItem } from './types';

/**
 * Banco de preguntas del constructor. `basic` marca las que usa la mayoria de
 * formularios: se muestran primero; el resto queda en "Más tipos de pregunta"
 * para no abrumar a quien crea su primer formulario. Los nombres evitan jerga
 * (UUID, Lookup, OCR, NPS...) o la explican entre paréntesis.
 */
export const FIELD_CATALOG: BuilderPaletteItem[] = [
  { category: 'Texto', type: 'TEXT', icon: '🔤', basic: true, label: 'Texto corto', description: 'Nombres, códigos o respuestas breves' },
  { category: 'Texto', type: 'DOCUMENT_ID', icon: '🪪', basic: true, label: 'Documento de identidad', description: 'Cédula, pasaporte, NIT o código' },
  { category: 'Texto', type: 'TEXTAREA', icon: '📝', basic: true, label: 'Texto largo', description: 'Observaciones y descripciones' },
  { category: 'Texto', type: 'EMAIL', icon: '✉️', basic: true, label: 'Correo electrónico', description: 'Revisa que el correo esté bien escrito' },
  { category: 'Texto', type: 'PHONE', icon: '📞', basic: true, label: 'Teléfono', description: 'Número de contacto' },
  { category: 'Texto', type: 'URL', icon: '🔗', label: 'Enlace web', description: 'Dirección de una página web' },
  { category: 'Números', type: 'NUMBER', icon: '🔢', basic: true, label: 'Número', description: 'Cantidades, edades, valores' },
  { category: 'Números', type: 'INTEGER', icon: '#️⃣', label: 'Número entero', description: 'Conteos exactos, sin decimales' },
  { category: 'Números', type: 'DECIMAL', icon: '⚖️', label: 'Número con decimales', description: 'Pesos, áreas y medidas' },
  { category: 'Números', type: 'PERCENTAGE', icon: '💯', label: 'Porcentaje', description: 'Valor entre 0 y 100' },
  { category: 'Números', type: 'CURRENCY', icon: '💲', label: 'Dinero', description: 'Valor en pesos u otra moneda' },
  { category: 'Opciones', type: 'BOOLEAN', icon: '✔️', basic: true, label: 'Sí / No', description: 'Pregunta de dos respuestas' },
  { category: 'Opciones', type: 'SELECT', icon: '🔘', basic: true, label: 'Elegir una opción', description: 'La persona marca solo una' },
  { category: 'Opciones', type: 'MULTISELECT', icon: '☑️', basic: true, label: 'Elegir varias opciones', description: 'La persona puede marcar varias' },
  { category: 'Opciones', type: 'DROPDOWN', icon: '🔽', label: 'Lista desplegable', description: 'Para listas largas de opciones' },
  { category: 'Fecha y hora', type: 'DATE', icon: '📅', basic: true, label: 'Fecha', description: 'Día, mes y año' },
  { category: 'Fecha y hora', type: 'TIME', icon: '⏰', label: 'Hora', description: 'Hora del día' },
  { category: 'Fecha y hora', type: 'DATETIME', icon: '🗓️', label: 'Fecha y hora', description: 'Día y hora juntos' },
  { category: 'Fecha y hora', type: 'YEAR', icon: '📆', label: 'Año', description: 'Solo el año' },
  { category: 'Fecha y hora', type: 'MONTH', icon: '📆', label: 'Mes', description: 'Mes y año' },
  { category: 'Fecha y hora', type: 'WEEK', icon: '📆', label: 'Semana', description: 'Semana del año' },
  { category: 'Fotos y archivos', type: 'IMAGE', icon: '📷', basic: true, label: 'Foto', description: 'Tomar o subir una fotografía' },
  { category: 'Fotos y archivos', type: 'SIGNATURE', icon: '✍️', basic: true, label: 'Firma', description: 'Firmar con el dedo en la pantalla' },
  { category: 'Fotos y archivos', type: 'FILE', icon: '📎', basic: true, label: 'Archivo adjunto', description: 'Subir un documento' },
  { category: 'Fotos y archivos', type: 'PDF', icon: '📄', label: 'Documento PDF', description: 'Soporte en PDF' },
  { category: 'Fotos y archivos', type: 'MULTIFILE', icon: '🗂️', label: 'Varios archivos', description: 'Conjunto de evidencias' },
  { category: 'Fotos y archivos', type: 'AUDIO', icon: '🎙️', label: 'Grabación de voz', description: 'Audio desde el micrófono' },
  { category: 'Fotos y archivos', type: 'VIDEO', icon: '🎥', label: 'Video', description: 'Grabar o subir un video' },
  { category: 'Mapa y ubicación', type: 'GPS', icon: '📍', basic: true, label: 'Ubicación GPS', description: 'Guarda dónde se llenó' },
  { category: 'Mapa y ubicación', type: 'GEOTRACE', icon: '〰️', label: 'Recorrido o ruta', description: 'Línea de varios puntos en el mapa' },
  { category: 'Mapa y ubicación', type: 'GEOSHAPE', icon: '⬠', label: 'Área en el mapa', description: 'Dibujar un polígono (predio, zona)' },
  { category: 'Escalas y opinión', type: 'RATING', icon: '⭐', label: 'Calificación con estrellas', description: 'De 1 a 5 estrellas' },
  { category: 'Escalas y opinión', type: 'LIKERT_5', icon: '📶', label: 'Escala de acuerdo (1 a 5)', description: 'Muy en desacuerdo … muy de acuerdo' },
  { category: 'Escalas y opinión', type: 'LIKERT_7', icon: '📶', label: 'Escala de acuerdo (1 a 7)', description: 'Escala más detallada' },
  { category: 'Escalas y opinión', type: 'NPS', icon: '👍', label: '¿Nos recomendaría? (0 a 10)', description: 'Índice de recomendación (NPS)' },
  { category: 'Escalas y opinión', type: 'RANKING', icon: '🥇', label: 'Ordenar por prioridad', description: 'La persona ordena las opciones' },
  { category: 'Escalas y opinión', type: 'RANGE', icon: '🎚️', label: 'Barra deslizante', description: 'Elegir un valor moviendo la barra' },
  { category: 'Escanear', type: 'BARCODE', icon: '▥', label: 'Código de barras', description: 'Escanear con la cámara' },
  { category: 'Escanear', type: 'QR', icon: '🔳', label: 'Código QR', description: 'Escanear con la cámara' },
  { category: 'Escanear', type: 'OCR', icon: '🔍', label: 'Leer texto de una foto', description: 'Extrae el texto de una imagen (OCR)' },
  { category: 'Escanear', type: 'FINGERPRINT', icon: '👆', label: 'Verificar con huella o rostro', description: 'Usa el desbloqueo del celular; no guarda la huella' },
  { category: 'Avanzadas', type: 'REPEAT', icon: '🔁', label: 'Grupo que se repite', description: 'Ej.: un bloque por cada miembro del hogar' },
  { category: 'Avanzadas', type: 'LINKED_SUBFORM', icon: '🧩', label: 'Subformulario enlazado', description: 'Cada fila se guarda como registro propio' },
  { category: 'Avanzadas', type: 'MATRIX', icon: '▦', label: 'Tabla de preguntas', description: 'Varias preguntas con la misma escala' },
  { category: 'Avanzadas', type: 'PARENT_CHILD', icon: '👪', label: 'Vincular a otro registro', description: 'Elegir un registro de otro formulario' },
  { category: 'Avanzadas', type: 'CALCULATE', icon: '🧮', label: 'Cálculo automático', description: 'Resultado calculado con otras respuestas' },
  { category: 'Avanzadas', type: 'REFERENCE', icon: '↗️', label: 'Dato de otro formulario', description: 'Muestra un dato vinculado' },
  { category: 'Avanzadas', type: 'LOOKUP', icon: '📥', label: 'Precargar desde otra fuente', description: 'Trae datos ya existentes' },
  { category: 'Avanzadas', type: 'HIDDEN', icon: '🙈', label: 'Dato oculto', description: 'Se guarda pero no se muestra' },
  { category: 'Automáticos (se llenan solos)', type: 'UUID', icon: '🆔', label: 'Identificador único', description: 'Código único generado solo (UUID)' },
  { category: 'Automáticos (se llenan solos)', type: 'RESPONSE_ID', icon: '🆔', label: 'Número de respuesta', description: 'Identificador del registro' },
  { category: 'Automáticos (se llenan solos)', type: 'SERIAL_NUMBER', icon: '🔢', label: 'Consecutivo', description: 'Número que asigna el servidor al guardar' },
  { category: 'Automáticos (se llenan solos)', type: 'INTERVIEW_DURATION', icon: '⏱️', label: 'Duración de la entrevista', description: 'Tiempo que tomó llenar' },
  { category: 'Automáticos (se llenan solos)', type: 'CAPTURED_BY', icon: '👤', label: 'Quién lo llenó', description: 'Usuario que capturó el registro' },
  { category: 'Automáticos (se llenan solos)', type: 'CHANGE_HISTORY', icon: '🕓', label: 'Historial de cambios', description: 'Quién cambió qué y cuándo' },
];

const BY_TYPE = new Map(FIELD_CATALOG.map((item) => [item.type, item]));

/** Nombre y emoji legibles de un tipo de pregunta, para no mostrar el código interno. */
export function fieldTypeInfo(type: string): { label: string; icon: string } {
  const item = BY_TYPE.get(type);
  return { label: item?.label ?? type, icon: item?.icon ?? '❔' };
}

/** Tipos que el servidor llena solo; no tienen control que mostrar en la vista previa. */
export const AUTOMATIC_TYPES = new Set(
  FIELD_CATALOG.filter((item) => item.category.startsWith('Automáticos') || ['HIDDEN', 'CALCULATE'].includes(item.type)).map((item) => item.type),
);
