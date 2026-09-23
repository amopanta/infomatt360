import type { ActaFieldOption } from '../acta/types';
import type { TemplateSummary } from '../records/api';
import type { IndicatorDefinition } from './catalogApi';

type Props = {
  value: IndicatorDefinition;
  templates: TemplateSummary[];
  fields: Record<string, ActaFieldOption[]>;
  onChange: (patch: Partial<IndicatorDefinition>) => void;
};

export function IndicatorSourcesEditor({ value, templates, fields, onChange }: Props) {
  const updateSource = (index: number, patch: Partial<IndicatorDefinition['sources'][number]>) => onChange({ sources: value.sources.map((row, i) => i === index ? { ...row, ...patch } : row) });
  return <div className="indicator-sources-editor">
    <label>Código del indicador<input value={value.code ?? ''} maxLength={40} onChange={(event) => onChange({ code: event.target.value })} placeholder="IND-001" /></label>
    {value.source_mode === 'automatic' && (value.sources.length ? <>
      <h4>Formularios asociados</h4>
      <label>Relación entre formularios<select value={value.combination} onChange={(event) => onChange({ combination: event.target.value as IndicatorDefinition['combination'] })}><option value="sum">Suma por formulario</option><option value="union">Unión, sin duplicados</option><option value="intersection">Intersección</option><option value="all">Cumple todos los formularios</option></select></label>
      <p>La llave debe identificar a la misma persona u hogar en cada formulario. Unión e intersección requieren una llave.</p>
      {value.sources.map((source, index) => <div className="indicator-source-row" key={index}>
        <label>Formulario<select value={source.template_id} onChange={(event) => updateSource(index, { template_id: event.target.value, key_field: null })}><option value="">Seleccionar formulario</option>{templates.map((template) => <option key={template.id} value={template.id}>{template.name}</option>)}</select></label>
        <label>Llave de relación<select value={source.key_field ?? ''} onChange={(event) => updateSource(index, { key_field: event.target.value || null })}><option value="">{value.combination === 'sum' ? 'Contar respuestas' : 'Seleccionar variable'}</option>{(fields[source.template_id] ?? []).map((field) => <option key={field.name} value={field.name}>{field.label} ({field.name})</option>)}</select></label>
        <label>Estado requerido<select value={source.required_status ?? ''} onChange={(event) => updateSource(index, { required_status: event.target.value || null })}><option value="">Cualquier respuesta enviada</option><option value="submitted">Enviado</option><option value="approved">Aprobado</option><option value="tech_approved">Aprobado técnicamente</option><option value="coordinator_approved">Aprobado por coordinación</option></select></label>
        <button type="button" disabled={value.sources.length <= 1} onClick={() => onChange({ sources: value.sources.filter((_, i) => i !== index) })}>Quitar</button>
      </div>)}
      <button type="button" onClick={() => onChange({ sources: [...value.sources, { template_id: templates[0]?.id ?? '', key_field: null, required_status: null }], combination: value.combination === 'single' ? 'union' : value.combination })}>+ Asociar otro formulario</button>
      <button type="button" onClick={() => onChange({ template_id: value.sources[0]?.template_id ?? null, sources: [], combination: 'single' })}>Usar un solo formulario</button>
    </> : <button type="button" onClick={() => onChange({ sources: [{ template_id: value.template_id ?? templates[0]?.id ?? '', key_field: null, required_status: null }, { template_id: '', key_field: null, required_status: null }], combination: 'union' })}>+ Relacionar varios formularios</button>)}
  </div>;
}
