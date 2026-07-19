import { describe, expect, it } from 'vitest';
import { mapFieldSchemaToTableauColumns, METADATA_COLUMNS, tableauDataTypeForComponent } from './schemaMapping';
import type { ExternalFieldSchema } from './types';

describe('tableauDataTypeForComponent', () => {
  it('mapea booleanos', () => {
    expect(tableauDataTypeForComponent('BOOLEAN')).toBe('bool');
  });

  it('mapea fechas', () => {
    expect(tableauDataTypeForComponent('DATE')).toBe('date');
    expect(tableauDataTypeForComponent('YEAR')).toBe('date');
  });

  it('mapea fecha y hora', () => {
    expect(tableauDataTypeForComponent('DATETIME')).toBe('datetime');
  });

  it('mapea enteros', () => {
    expect(tableauDataTypeForComponent('INTEGER')).toBe('int');
    expect(tableauDataTypeForComponent('SERIAL_NUMBER')).toBe('int');
  });

  it('mapea decimales', () => {
    expect(tableauDataTypeForComponent('NUMBER')).toBe('float');
    expect(tableauDataTypeForComponent('CURRENCY')).toBe('float');
  });

  it('cae a string para un tipo no mapeado', () => {
    expect(tableauDataTypeForComponent('REPEAT')).toBe('string');
    expect(tableauDataTypeForComponent('GPS')).toBe('string');
  });
});

describe('mapFieldSchemaToTableauColumns', () => {
  const baseField = (overrides: Partial<ExternalFieldSchema>): ExternalFieldSchema => ({
    id: 'c1', template_id: 't1', component_type: 'TEXT', name: 'nombre', label: 'Nombre', ...overrides,
  });

  it('siempre antepone las 6 columnas fijas de metadata, en orden', () => {
    const columns = mapFieldSchemaToTableauColumns([]);
    expect(columns).toEqual(METADATA_COLUMNS);
  });

  it('agrega una columna por campo, en el orden recibido', () => {
    const fields = [baseField({ name: 'nombre', label: 'Nombre' }), baseField({ id: 'c2', name: 'edad', label: 'Edad', component_type: 'INTEGER' })];
    const columns = mapFieldSchemaToTableauColumns(fields);
    expect(columns.slice(METADATA_COLUMNS.length)).toEqual([
      { id: 'nombre', alias: 'Nombre', dataType: 'string' },
      { id: 'edad', alias: 'Edad', dataType: 'int' },
    ]);
  });

  it('deduplica por name -- gana el ultimo cuando dos campos comparten nombre', () => {
    const fields = [
      baseField({ id: 'c1', name: 'nombre', label: 'Nombre viejo', component_type: 'TEXT' }),
      baseField({ id: 'c2', name: 'nombre', label: 'Nombre nuevo', component_type: 'INTEGER' }),
    ];
    const columns = mapFieldSchemaToTableauColumns(fields);
    const nombreColumns = columns.filter((column) => column.id === 'nombre');
    expect(nombreColumns).toEqual([{ id: 'nombre', alias: 'Nombre nuevo', dataType: 'int' }]);
  });
});
