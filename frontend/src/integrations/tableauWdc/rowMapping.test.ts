import { describe, expect, it } from 'vitest';
import { METADATA_COLUMNS } from './schemaMapping';
import { mapTabularPageToTableauRows } from './rowMapping';
import type { ExternalRecordTabularPage, TableauColumnDef } from './types';

const columns: TableauColumnDef[] = [...METADATA_COLUMNS, { id: 'nombre', alias: 'Nombre', dataType: 'string' }, { id: 'edad', alias: 'Edad', dataType: 'int' }];

function page(overrides: Partial<ExternalRecordTabularPage> = {}): ExternalRecordTabularPage {
  return {
    template_id: 't1',
    columns: ['nombre', 'edad'],
    items: [{ record_id: 'r1', status: 'approved', submitted_by: 'u1', participant_id: null, created_at: '2026-07-01T00:00:00', updated_at: '2026-07-02T00:00:00', fields: { nombre: 'Ana', edad: 30 } }],
    total: 1,
    limit: 25,
    offset: 0,
    ...overrides,
  };
}

describe('mapTabularPageToTableauRows', () => {
  it('aplana el sobre fijo y los campos del formulario en un objeto plano', () => {
    const rows = mapTabularPageToTableauRows(page(), columns);
    expect(rows).toEqual([{ record_id: 'r1', status: 'approved', submitted_by: 'u1', participant_id: null, created_at: '2026-07-01T00:00:00', updated_at: '2026-07-02T00:00:00', nombre: 'Ana', edad: 30 }]);
  });

  it('un valor ausente/null en fields llega como null, no falta la clave', () => {
    const rows = mapTabularPageToTableauRows(page({ items: [{ record_id: 'r1', status: 'approved', created_at: 'x', updated_at: 'y', fields: { nombre: null } }] }), columns);
    expect(rows[0].nombre).toBeNull();
    expect('edad' in rows[0]).toBe(true);
    expect(rows[0].edad).toBeNull();
  });

  it('un campo de formulario que colisiona con una columna de metadata no sobrescribe el sobre fijo', () => {
    const collidingColumns: TableauColumnDef[] = [...METADATA_COLUMNS, { id: 'status', alias: 'Estado (campo)', dataType: 'string' }];
    const rows = mapTabularPageToTableauRows(page({ items: [{ record_id: 'r1', status: 'approved', created_at: 'x', updated_at: 'y', fields: { status: 'valor-de-campo' } }] }), collidingColumns);
    expect(rows[0].status).toBe('approved');
  });

  it('un valor no escalar en una columna string se serializa a JSON', () => {
    const rows = mapTabularPageToTableauRows(page({ items: [{ record_id: 'r1', status: 'approved', created_at: 'x', updated_at: 'y', fields: { nombre: { type: 'Point', coordinates: [1, 2] } } }] }), columns);
    expect(rows[0].nombre).toBe('{"type":"Point","coordinates":[1,2]}');
  });
});
