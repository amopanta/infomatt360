import { METADATA_COLUMNS } from './schemaMapping';
import type { ExternalRecordTabularPage, TableauColumnDef } from './types';

const METADATA_COLUMN_IDS = new Set(METADATA_COLUMNS.map((column) => column.id));

/** Aplana el sobre fijo (record_id/status/...) y los campos del formulario
 * en un solo objeto plano por fila, en la forma que espera `table.appendRows`
 * de la API de Tableau. Si un campo de formulario colisiona de nombre con
 * una columna de metadata, la metadata gana -- no se sobrescribe el sobre
 * fijo (esa es la razon por la que el backend devuelve `fields` anidado en
 * vez de aplanado, ver docs/114). Un valor no escalar (REPEAT/MATRIX/GPS)
 * que caiga en una columna 'string' se serializa a JSON en vez de pasar el
 * objeto/arreglo crudo. */
export function mapTabularPageToTableauRows(page: ExternalRecordTabularPage, columns: TableauColumnDef[]): Array<Record<string, unknown>> {
  return page.items.map((item) => {
    const row: Record<string, unknown> = {
      record_id: item.record_id,
      status: item.status,
      submitted_by: item.submitted_by ?? null,
      participant_id: item.participant_id ?? null,
      created_at: item.created_at,
      updated_at: item.updated_at,
    };
    for (const column of columns) {
      if (METADATA_COLUMN_IDS.has(column.id)) continue;
      const value = item.fields[column.id] ?? null;
      row[column.id] = column.dataType === 'string' && value !== null && typeof value === 'object' ? JSON.stringify(value) : value;
    }
    return row;
  });
}
