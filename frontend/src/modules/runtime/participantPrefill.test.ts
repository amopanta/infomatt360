import { describe, expect, it } from 'vitest';
import { prefillParticipantAnswers } from './participantPrefill';
import type { RuntimeTemplate } from './types';

const template: RuntimeTemplate = {
  template_id: 'f', name: 'Prueba', status: 'published', pages: [{ id: 'p', title: 'General', sections: [{ id: 's', title: 'Datos', rows: [{ id: 'r', columns: [{ id: 'c', desktop_width: 12, tablet_width: 12, mobile_width: 12, components: [
    { id: '1', type: 'TEXT', name: 'nombre', label: 'Nombre', config_json: JSON.stringify({ participant_field: 'full_name' }) },
    { id: '2', type: 'PHONE', name: 'telefono', label: 'Teléfono', config_json: JSON.stringify({ participant_field: 'phone' }) },
  ] }] }] }] }],
};

describe('prefill de participante', () => {
  const person = { id: 'p1', full_name: 'Ana', metadata_json: JSON.stringify({ phone: '3001234567' }) };

  it('precarga los datos sin reemplazar una corrección hecha por el gestor', () => {
    expect(prefillParticipantAnswers(template, person, { nombre: 'Ana corregida' })).toMatchObject({ nombre: 'Ana corregida', telefono: '3001234567' });
  });

  it('no importa respuestas de otro participante al iniciar con un borrador vacío', () => {
    expect(prefillParticipantAnswers(template, { id: 'p2', full_name: 'Luis', metadata_json: '{}' }, {})).toMatchObject({ nombre: 'Luis' });
  });
});
