import type { ExternalFieldSchema, TableauColumnDataType, TableauColumnDef } from './types';

/** Columnas fijas del sobre que trae cada fila de /external-api/records/tabular
 * (docs/114), siempre presentes independientemente del formulario. */
export const METADATA_COLUMNS: TableauColumnDef[] = [
  { id: 'record_id', alias: 'ID de registro', dataType: 'string' },
  { id: 'status', alias: 'Estado', dataType: 'string' },
  { id: 'submitted_by', alias: 'Capturado por', dataType: 'string' },
  { id: 'participant_id', alias: 'Participante', dataType: 'string' },
  { id: 'created_at', alias: 'Fecha de creación', dataType: 'datetime' },
  { id: 'updated_at', alias: 'Última actualización', dataType: 'datetime' },
];

const BOOLEAN_TYPES = new Set(['BOOLEAN']);
const DATE_TYPES = new Set(['DATE', 'YEAR', 'MONTH', 'WEEK']);
const DATETIME_TYPES = new Set(['DATETIME']);
const INT_TYPES = new Set(['INTEGER', 'SERIAL_NUMBER', 'NPS', 'RATING']);
const FLOAT_TYPES = new Set(['NUMBER', 'DECIMAL', 'PERCENTAGE', 'CURRENCY', 'RANGE']);

/** Mismo catalogo de tipos numericos/fecha ya usado en el resto del
 * frontend (ver reports/types.ts, docs/111) -- aqui traducido al vocabulario
 * de tipos de columna que espera la API JS de Tableau. Cualquier tipo no
 * mapeado explicitamente (REPEAT, MATRIX, GPS, SIGNATURE, etc.) cae a
 * 'string', consistente con como esos campos ya viajan como JSON crudo. */
export function tableauDataTypeForComponent(componentType: string): TableauColumnDataType {
  const type = componentType.toUpperCase();
  if (BOOLEAN_TYPES.has(type)) return 'bool';
  if (DATETIME_TYPES.has(type)) return 'datetime';
  if (DATE_TYPES.has(type)) return 'date';
  if (INT_TYPES.has(type)) return 'int';
  if (FLOAT_TYPES.has(type)) return 'float';
  return 'string';
}

/** Antepone las columnas fijas de metadata y agrega una columna por campo
 * del formulario, en el orden recibido (ya viene ordenado por sort_order
 * desde el backend). Si dos campos comparten `name` (BuilderComponent.name
 * no es unico a nivel de base de datos), gana el ultimo -- una sola columna
 * Tableau por nombre, nunca dos con el mismo id. */
export function mapFieldSchemaToTableauColumns(fields: ExternalFieldSchema[]): TableauColumnDef[] {
  const fieldColumns = new Map<string, TableauColumnDef>();
  for (const field of fields) {
    fieldColumns.set(field.name, { id: field.name, alias: field.label || field.name, dataType: tableauDataTypeForComponent(field.component_type) });
  }
  return [...METADATA_COLUMNS, ...fieldColumns.values()];
}
