import { useEffect, useState } from 'react';
import { AppShell } from '../../components/AppShell';
import { useI18n } from '../../i18n';
import { fetchTemplateFields } from '../acta/api';
import type { ActaFieldOption } from '../acta/types';
import { PROJECT_KEY, hasAnyCurrentProjectPermission } from '../auth/session';
import { fetchProjectTemplates } from '../records/api';
import type { TemplateSummary } from '../records/api';
import { IndicatorSourcesEditor } from './IndicatorSourcesEditor';
import { applyIndicatorWorkbook, downloadIndicatorWorkbookTemplate, listLibraryIndicators, previewIndicatorWorkbook, saveLibraryIndicator } from './catalogApi';
import type { IndicatorDefinition, IndicatorImportPreview, LibraryIndicator } from './catalogApi';

function blank(templateId = ''): IndicatorDefinition {
  return { code: '', title: '', source_mode: 'automatic', template_id: templateId || null, value_field: null, aggregation: 'count', goal: 0, manual_actual: null, unit: '', municipality_field: null, view_kind: 'progress', sources: [], combination: 'single' };
}

export function IndicatorLibraryApp() {
  const { t } = useI18n();
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';
  const canEdit = hasAnyCurrentProjectPermission(['builder.write']);
  const [rows, setRows] = useState<LibraryIndicator[]>([]);
  const [templates, setTemplates] = useState<TemplateSummary[]>([]);
  const [fields, setFields] = useState<Record<string, ActaFieldOption[]>>({});
  const [selectedId, setSelectedId] = useState('');
  const [draft, setDraft] = useState<IndicatorDefinition | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<IndicatorImportPreview | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    if (!projectId) return;
    Promise.all([listLibraryIndicators(projectId), fetchProjectTemplates(projectId)]).then(([items, forms]) => { setRows(items); setTemplates(forms); }).catch((error: Error) => setMessage(error.message));
  }, [projectId]);
  useEffect(() => {
    if (!draft) return;
    [draft.template_id, ...draft.sources.map((source) => source.template_id)].forEach((id) => {
      if (id && !fields[id]) fetchTemplateFields(id).then((items) => setFields((current) => ({ ...current, [id]: items }))).catch(() => setFields((current) => ({ ...current, [id]: [] })));
    });
  }, [draft, fields]);

  async function save() {
    if (!draft) return;
    setBusy(true); setMessage('');
    try {
      const saved = await saveLibraryIndicator(projectId, draft, selectedId || undefined);
      setRows(await listLibraryIndicators(projectId)); setSelectedId(saved.id); setDraft(saved.definition); setMessage(t('reports.indicators.savedMessage'));
    } catch (error) { setMessage(error instanceof Error ? error.message : t('reports.indicators.saveError')); }
    finally { setBusy(false); }
  }

  async function previewFile() {
    if (!file) return;
    setBusy(true); setMessage('');
    try { const result = await previewIndicatorWorkbook(projectId, file); setPreview(result); setMessage(t('reports.indicators.validPreview', { count: result.indicators.length, errors: result.errors.length })); }
    catch (error) { setMessage(error instanceof Error ? error.message : t('reports.indicators.validateError')); }
    finally { setBusy(false); }
  }

  async function applyFile() {
    if (!file || !preview || preview.errors.length) return;
    setBusy(true); setMessage('');
    try { const imported = await applyIndicatorWorkbook(projectId, file); setRows(await listLibraryIndicators(projectId)); setFile(null); setPreview(null); setMessage(t('reports.indicators.importedCount', { count: imported.length })); }
    catch (error) { setMessage(error instanceof Error ? error.message : t('reports.indicators.importError')); }
    finally { setBusy(false); }
  }

  return <AppShell title={t('reports.indicators.title')}><main className="reports-shell reports-studio report-catalog">
    <header className="reports-header"><div><h2>{t('reports.indicators.title')}</h2><p>{t('reports.indicators.description')}</p></div><div className="reports-actions"><a href="/reports/catalog">{t('reports.indicators.backToReports')}</a>{canEdit && <button type="button" onClick={() => { setSelectedId(''); setDraft(blank(templates[0]?.id)); }}>{t('reports.indicators.newIndicator')}</button>}</div></header>
    {message && <p role="status" className="catalog-message">{message}</p>}
    {canEdit && <section className="catalog-editor indicator-import"><h3>{t('reports.indicators.importFromExcel')}</h3><button type="button" onClick={() => void downloadIndicatorWorkbookTemplate(projectId)}>{t('reports.indicators.downloadTemplate')}</button><input type="file" accept=".xlsx" aria-label={t('reports.indicators.fileAria')} onChange={(event) => { setFile(event.target.files?.[0] ?? null); setPreview(null); }} /><button type="button" disabled={!file || busy} onClick={() => void previewFile()}>{t('reports.indicators.validateFile')}</button>{preview && <div><strong>{t('reports.indicators.validAndErrors', { valid: preview.indicators.length, errors: preview.errors.length })}</strong>{preview.errors.map((error) => <p key={error.row}>{t('reports.indicators.rowError', { row: error.row, error: error.error })}</p>)}<button type="button" disabled={busy || !!preview.errors.length || !preview.indicators.length} onClick={() => void applyFile()}>{t('reports.indicators.importValidated')}</button></div>}</section>}
    <div className="catalog-layout"><aside className="catalog-list"><h3>{t('reports.indicators.projectIndicators')}</h3>{rows.map((row) => <button type="button" key={row.id} className={selectedId === row.id ? 'active' : ''} onClick={() => { setSelectedId(row.id); setDraft({ ...row.definition }); }}><strong>{row.definition.code} · {row.definition.title}</strong><small>{t('reports.indicators.goalLabel')}: {row.definition.goal.toLocaleString('es-CO')} {row.definition.unit} · {row.definition.source_mode === 'manual' ? t('reports.indicators.manualLabel') : t('reports.indicators.formCount', { count: row.definition.sources.length || 1 })}</small></button>)}{!rows.length && <p>{t('reports.indicators.noIndicatorsYet')}</p>}</aside>
      <section className="catalog-content">{draft ? <div className="catalog-editor"><h2>{selectedId ? t('reports.indicators.editIndicator') : t('reports.indicators.newIndicatorTitle')}</h2><label>{t('reports.indicators.nameLabel')}<input value={draft.title} onChange={(event) => setDraft({ ...draft, title: event.target.value })} /></label><div className="catalog-form-grid"><label>{t('reports.indicators.sourceLabel')}<select value={draft.source_mode} onChange={(event) => setDraft({ ...draft, source_mode: event.target.value as IndicatorDefinition['source_mode'], manual_actual: event.target.value === 'manual' ? draft.manual_actual ?? 0 : null })}><option value="automatic">{t('reports.indicators.sourceAutomatic')}</option><option value="manual">{t('reports.indicators.sourceManual')}</option></select></label><label>{t('reports.indicators.goalLabel')}<input type="number" min="0" value={draft.goal} onChange={(event) => setDraft({ ...draft, goal: Number(event.target.value) })} /></label><label>{t('reports.indicators.unitLabel')}<input value={draft.unit} onChange={(event) => setDraft({ ...draft, unit: event.target.value })} /></label>{draft.source_mode === 'manual' && <label>{t('reports.indicators.currentProgress')}<input type="number" min="0" value={draft.manual_actual ?? 0} onChange={(event) => setDraft({ ...draft, manual_actual: Number(event.target.value) })} /></label>}</div>
        {draft.source_mode === 'automatic' && !draft.sources.length && <div className="catalog-form-grid"><label>{t('reports.indicators.formLabel')}<select value={draft.template_id ?? ''} onChange={(event) => setDraft({ ...draft, template_id: event.target.value || null, value_field: null })}><option value="">{t('reports.indicators.selectOption')}</option>{templates.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label>{t('reports.indicators.operationLabel')}<select value={draft.aggregation} onChange={(event) => setDraft({ ...draft, aggregation: event.target.value as IndicatorDefinition['aggregation'] })}><option value="count">{t('reports.indicators.opCount')}</option><option value="unique_count">{t('reports.indicators.opUniqueCount')}</option><option value="sum">{t('reports.indicators.opSum')}</option><option value="average">{t('reports.indicators.opAverage')}</option></select></label><label>{t('reports.indicators.variableLabel')}<select value={draft.value_field ?? ''} onChange={(event) => setDraft({ ...draft, value_field: event.target.value || null })}><option value="">{draft.aggregation === 'count' ? t('reports.indicators.eachResponse') : t('reports.indicators.selectVariable')}</option>{(fields[draft.template_id ?? ''] ?? []).map((field) => <option key={field.name} value={field.name}>{field.label} ({field.name})</option>)}</select></label></div>}
        <IndicatorSourcesEditor value={draft} templates={templates} fields={fields} onChange={(patch) => setDraft({ ...draft, ...patch })} />
        {canEdit && <div className="catalog-editor-actions"><button type="button" disabled={busy || !draft.code.trim() || !draft.title.trim() || (draft.source_mode === 'automatic' && (draft.sources.length ? draft.sources.some((source) => !source.template_id || (['union', 'intersection', 'all'].includes(draft.combination) && !source.key_field)) : !draft.template_id))} onClick={() => void save()}>{busy ? t('reports.indicators.saving') : t('reports.indicators.saveIndicator')}</button></div>}</div> : <div className="reports-empty"><h3>{t('reports.indicators.selectOrCreate')}</h3><p>{t('reports.indicators.selectOrCreateDesc')}</p></div>}</section>
    </div>
  </main></AppShell>;
}
