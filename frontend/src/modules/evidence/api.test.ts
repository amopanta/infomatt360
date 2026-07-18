import { describe, expect, it } from 'vitest';
import { buildEvidenceBatchPayload } from './api';

describe('buildEvidenceBatchPayload', () => {
  it('traduce assetIds a snake_case cuando hay seleccion manual', () => {
    expect(buildEvidenceBatchPayload({ assetIds: ['a1', 'a2'], participantId: 'p1' })).toEqual({
      asset_ids: ['a1', 'a2'],
      participant_id: 'p1',
      template_id: null,
      status: null,
      created_by: null,
      date_from: null,
      date_to: null,
    });
  });

  it('resuelve por filtros cuando no hay asset_ids, con rango de fecha expandido a inicio/fin de dia', () => {
    expect(
      buildEvidenceBatchPayload({
        participantId: 'p1',
        templateId: 't1',
        status: 'approved',
        createdBy: 'u1',
        dateFrom: '2026-07-01',
        dateTo: '2026-07-18',
      }),
    ).toEqual({
      asset_ids: null,
      participant_id: 'p1',
      template_id: 't1',
      status: 'approved',
      created_by: 'u1',
      date_from: '2026-07-01T00:00:00',
      date_to: '2026-07-18T23:59:59',
    });
  });

  it('un arreglo de assetIds vacio cuenta como "sin seleccion manual"', () => {
    expect(buildEvidenceBatchPayload({ assetIds: [], status: 'approved' })).toEqual({
      asset_ids: null,
      participant_id: null,
      template_id: null,
      status: 'approved',
      created_by: null,
      date_from: null,
      date_to: null,
    });
  });

  it('sin ningun filtro ni seleccion, todo queda en null', () => {
    expect(buildEvidenceBatchPayload({})).toEqual({
      asset_ids: null,
      participant_id: null,
      template_id: null,
      status: null,
      created_by: null,
      date_from: null,
      date_to: null,
    });
  });
});
