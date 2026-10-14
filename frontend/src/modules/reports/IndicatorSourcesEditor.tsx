import { useI18n } from '../../i18n';
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
  const { t } = useI18n();
  const updateSource = (index: number, patch: Partial<IndicatorDefinition['sources'][number]>) => onChange({ sources: value.sources.map((row, i) => i === index ? { ...row, ...patch } : row) });
  return <div className="indicator-sources-editor">
    <label>{t('reports.sources.indicatorCode')}<input value={value.code ?? ''} maxLength={40} onChange={(event) => onChange({ code: event.target.value })} placeholder={t('reports.sources.codePlaceholder')} /></label>
    {value.source_mode === 'automatic' && (value.sources.length ? <>
      <h4>{t('reports.sources.associatedForms')}</h4>
      <label>{t('reports.sources.formRelation')}<select value={value.combination} onChange={(event) => onChange({ combination: event.target.value as IndicatorDefinition['combination'] })}><option value="sum">{t('reports.sources.combinationSum')}</option><option value="union">{t('reports.sources.combinationUnion')}</option><option value="intersection">{t('reports.sources.combinationIntersection')}</option><option value="all">{t('reports.sources.combinationAll')}</option></select></label>
      <p>{t('reports.sources.keyDescription')}</p>
      {value.sources.map((source, index) => <div className="indicator-source-row" key={index}>
        <label>{t('reports.sources.formLabel')}<select value={source.template_id} onChange={(event) => updateSource(index, { template_id: event.target.value, key_field: null })}><option value="">{t('reports.sources.selectForm')}</option>{templates.map((template) => <option key={template.id} value={template.id}>{template.name}</option>)}</select></label>
        <label>{t('reports.sources.keyField')}<select value={source.key_field ?? ''} onChange={(event) => updateSource(index, { key_field: event.target.value || null })}><option value="">{value.combination === 'sum' ? t('reports.sources.countResponses') : t('reports.sources.selectVariable')}</option>{(fields[source.template_id] ?? []).map((field) => <option key={field.name} value={field.name}>{field.label} ({field.name})</option>)}</select></label>
        <label>{t('reports.sources.requiredStatus')}<select value={source.required_status ?? ''} onChange={(event) => updateSource(index, { required_status: event.target.value || null })}><option value="">{t('reports.sources.anySubmitted')}</option><option value="submitted">{t('reports.sources.statusSubmitted')}</option><option value="approved">{t('reports.sources.statusApproved')}</option><option value="tech_approved">{t('reports.sources.statusTechApproved')}</option><option value="coordinator_approved">{t('reports.sources.statusCoordinatorApproved')}</option></select></label>
        <button type="button" disabled={value.sources.length <= 1} onClick={() => onChange({ sources: value.sources.filter((_, i) => i !== index) })}>{t('reports.sources.remove')}</button>
      </div>)}
      <button type="button" onClick={() => onChange({ sources: [...value.sources, { template_id: templates[0]?.id ?? '', key_field: null, required_status: null }], combination: value.combination === 'single' ? 'union' : value.combination })}>{t('reports.sources.addForm')}</button>
      <button type="button" onClick={() => onChange({ template_id: value.sources[0]?.template_id ?? null, sources: [], combination: 'single' })}>{t('reports.sources.useSingleForm')}</button>
    </> : <button type="button" onClick={() => onChange({ sources: [{ template_id: value.template_id ?? templates[0]?.id ?? '', key_field: null, required_status: null }, { template_id: '', key_field: null, required_status: null }], combination: 'union' })}>{t('reports.sources.relateMultiple')}</button>)}
  </div>;
}
