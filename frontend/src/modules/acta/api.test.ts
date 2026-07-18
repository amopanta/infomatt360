import { describe, expect, it } from 'vitest';
import { buildBatchPayload } from './api';

describe('buildBatchPayload', () => {
  it('traduce record_ids a snake_case cuando hay seleccion manual', () => {
    expect(buildBatchPayload({ recordIds: ['r1', 'r2'] })).toEqual({
      record_ids: ['r1', 'r2'],
      search: null,
      status: null,
      unlinked_only: false,
    });
  });

  it('resuelve por filtro cuando no hay record_ids', () => {
    expect(buildBatchPayload({ search: 'ana', status: 'submitted', unlinkedOnly: true })).toEqual({
      record_ids: null,
      search: 'ana',
      status: 'submitted',
      unlinked_only: true,
    });
  });

  it('un arreglo de record_ids vacio cuenta como "sin seleccion manual"', () => {
    expect(buildBatchPayload({ recordIds: [], status: 'submitted' })).toEqual({
      record_ids: null,
      search: null,
      status: 'submitted',
      unlinked_only: false,
    });
  });

  it('sin ningun filtro ni seleccion, todo queda en null/false', () => {
    expect(buildBatchPayload({})).toEqual({
      record_ids: null,
      search: null,
      status: null,
      unlinked_only: false,
    });
  });
});
