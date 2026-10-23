import { useEffect, useState } from 'react';
import { AppShell } from '../../components/AppShell';
import { Icon } from '../../components/Icon';
import { useI18n } from '../../i18n';
import { fetchTemplateFields } from '../acta/api';
import type { ActaFieldOption } from '../acta/types';
import { PROJECT_KEY, hasAnyCurrentProjectPermission } from '../auth/session';
import { fetchProjectTemplates } from '../records/api';
import type { TemplateSummary } from '../records/api';
import { CatalogReportView } from './CatalogReportView';
import { CommitteeEditor } from './CommitteeEditor';
import { CommitteeReportView } from './CommitteeReportView';
import { IndicatorSourcesEditor } from './IndicatorSourcesEditor';
import { blankCommittee, getCatalog, issueReportLink, listCatalog, listLibraryIndicators, listReportLinks, revokeReportLink, saveCatalog } from './catalogApi';
import type { CatalogReport, CatalogReportConfig, CatalogResult, IndicatorDefinition, LibraryIndicator, ReportLink } from './catalogApi';

function blankIndicator(templateId = ''): IndicatorDefinition {
  return { code: '', sources: [], combination: 'single', title: '', source_mode: 'automatic', template_id: templateId || null, value_field: null, aggregation: 'count', goal: 0, manual_actual: null, unit: '', municipality_field: null, view_kind: 'progress' };
}

function localDateInput(value: string | null): string {
  if (!value) return '';
  const date = new Date(value);
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}

export function ReportCatalogApp() {
  const { t } = useI18n();
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';
  const canEdit = hasAnyCurrentProjectPermission(['builder.write']);
  const [reports, setReports] = useState<CatalogReport[]>([]);
  const [library, setLibrary] = useState<LibraryIndicator[]>([]);
  const [templates, setTemplates] = useState<TemplateSummary[]>([]);
  const [fields, setFields] = useState<Record<string, ActaFieldOption[]>>({});
  const [selectedId, setSelectedId] = useState('');
  const [result, setResult] = useState<CatalogResult | null>(null);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<CatalogReportConfig | null>(null);
  const [links, setLinks] = useState<ReportLink[]>([]);
  const [issuedUrl, setIssuedUrl] = useState('');
  const [message, setMessage] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!projectId) return;
    listCatalog(projectId).then(setReports).catch((error: Error) => setMessage(error.message));
    listLibraryIndicators(projectId).then(setLibrary).catch((error: Error) => setMessage(error.message));
    fetchProjectTemplates(projectId).then(setTemplates).catch((error: Error) => setMessage(error.message));
  }, [projectId]);

  useEffect(() => {
    const templateIds = new Set([...templates.map((item) => item.id), ...(draft?.indicators.flatMap((item) => [item.template_id, ...item.sources.map((row) => row.template_id)]) ?? [])]);
    templateIds.forEach((id) => { if (id && !fields[id]) fetchTemplateFields(id).then((items) => setFields((current) => ({ ...current, [id]: items }))).catch(() => setFields((current) => ({ ...current, [id]: [] }))); });
  }, [templates, draft, fields]);

  async function open(reportId: string) {
    setSelectedId(reportId); setEditing(false); setIssuedUrl(''); setMessage('');
    try { const [data, reportLinks] = await Promise.all([getCatalog(reportId), canEdit ? listReportLinks(reportId) : Promise.resolve([])]); setResult(data); setLinks(reportLinks); }
    catch (error) { setMessage(error instanceof Error ? error.message : t('reports.catalog.openError')); }
  }

  function startNew(kind: CatalogReportConfig['report_kind'] = 'indicators') {
    setSelectedId(''); setResult(null); setLinks([]); setIssuedUrl(''); setMessage('');
    setDraft({ project_id: projectId, name: '', description: '', report_kind: kind, committee: blankCommittee(), starts_at: null, ends_at: null, indicators: library.length ? [] : [blankIndicator(templates[0]?.id)], indicator_ids: [] });
    setEditing(true);
  }

  /** Modelos listos para no armar un reporte desde cero (docs/150): se llenan
   * con los formularios del proyecto y la persona solo ajusta las metas. */
  function startFromModel(model: 'progress' | 'territory') {
    const published = templates.filter((item) => item.status === 'published');
    const forms = published.length ? published : templates;
    const indicators = model === 'progress'
      ? forms.map((form) => ({ ...blankIndicator(form.id), title: form.name, goal: Math.max(10, (form.submissions_count ?? 0) * 2), unit: t('reports.catalog.modelResponses') }))
      : forms.slice(0, 1).map((form) => {
        const municipality = (fields[form.id] ?? []).find((field) => /munic|ciudad|territ/i.test(`${field.name} ${field.label}`));
        return { ...blankIndicator(form.id), title: form.name, goal: 100, unit: t('reports.catalog.modelResponses'), municipality_field: municipality?.name ?? null, view_kind: 'bar' as const };
      });
    startNew();
    setDraft((current) => current ? { ...current, name: t(model === 'progress' ? 'reports.catalog.modelProgressName' : 'reports.catalog.modelTerritoryName'), indicators: indicators.length ? indicators : current.indicators } : current);
  }

  function startEdit() {
    const report = reports.find((item) => item.id === selectedId);
    if (!report) return;
    setDraft({ project_id: report.project_id, name: report.name, description: report.description, report_kind: report.report_kind ?? 'indicators', committee: report.committee ?? blankCommittee(), starts_at: localDateInput(report.starts_at), ends_at: localDateInput(report.ends_at), indicators: report.indicators.map((item) => ({ ...item })), indicator_ids: report.indicator_ids ?? [] });
    setEditing(true);
  }

  function changeIndicator(index: number, patch: Partial<IndicatorDefinition>) {
    setDraft((current) => current ? { ...current, indicators: current.indicators.map((item, itemIndex) => itemIndex === index ? { ...item, ...patch } : item) } : current);
  }

  async function save() {
    if (!draft) return;
    setSaving(true); setMessage('');
    try {
      const saved = await saveCatalog({ ...draft, starts_at: draft.starts_at ? new Date(draft.starts_at).toISOString() : null, ends_at: draft.ends_at ? new Date(draft.ends_at).toISOString() : null }, selectedId || undefined);
      setReports(await listCatalog(projectId));
      setEditing(false); setDraft(null);
      await open(saved.id);
    } catch (error) { setMessage(error instanceof Error ? error.message : t('reports.catalog.saveError')); }
    finally { setSaving(false); }
  }

  async function share() {
    if (!selectedId) return;
    setMessage('');
    try {
      const issued = await issueReportLink(selectedId);
      setIssuedUrl(`${window.location.origin}/public-report/${issued.token}`);
      setLinks(await listReportLinks(selectedId));
    } catch (error) { setMessage(error instanceof Error ? error.message : t('reports.catalog.linkError')); }
  }

  async function revoke(linkId: string) {
    if (!selectedId) return;
    try { await revokeReportLink(selectedId, linkId); setLinks(await listReportLinks(selectedId)); setIssuedUrl(''); }
    catch (error) { setMessage(error instanceof Error ? error.message : t('reports.catalog.revokeError')); }
  }

  return <AppShell title={t('reports.title')}><main className="reports-shell reports-studio report-catalog">
    <header className="reports-header"><div><h2>{t('reports.catalog.title')}</h2><p>{t('reports.catalog.description')}</p></div><div className="reports-actions"><a href="/reports">{t('reports.catalog.backToBoard')}</a>{canEdit && <button type="button" onClick={() => startNew()}>{t('reports.catalog.createReport')}</button>}{canEdit && <button type="button" onClick={() => startNew('committee')}>{t('reports.catalog.createCommittee')}</button>}</div></header>
    {message && <p role="alert" className="catalog-message">{message}</p>}
    <div className="catalog-layout"><aside className="catalog-list"><h3>{t('reports.catalog.myReports')}</h3>{reports.length ? reports.map((item) => <button type="button" className={selectedId === item.id ? 'active' : ''} key={item.id} onClick={() => void open(item.id)}><strong>{item.name}</strong><small>{item.report_kind === 'committee' ? t('reports.catalog.committeePrefix') : ''}{t('reports.catalog.indicatorCount', { count: item.indicators.length + (item.indicator_ids?.length ?? 0) })}</small></button>) : <p>{t('reports.catalog.noReportsYet')}</p>}</aside>
      <section className="catalog-content">{editing && draft ? <div className="catalog-editor"><h2>{selectedId ? t('reports.catalog.editReport') : t('reports.catalog.newReport')}</h2><label>{t('reports.catalog.reportNameLabel')}<input value={draft.name} maxLength={180} onChange={(event) => setDraft({ ...draft, name: event.target.value })} /></label><label>{t('reports.catalog.descriptionLabel')}<textarea value={draft.description} maxLength={1000} onChange={(event) => setDraft({ ...draft, description: event.target.value })} /></label><div className="catalog-date-grid"><label>{t('reports.catalog.fromLabel')}<input type="datetime-local" value={draft.starts_at?.slice(0, 16) ?? ''} onChange={(event) => setDraft({ ...draft, starts_at: event.target.value || null })} /></label><label>{t('reports.catalog.toLabel')}<input type="datetime-local" value={draft.ends_at?.slice(0, 16) ?? ''} onChange={(event) => setDraft({ ...draft, ends_at: event.target.value || null })} /></label></div>
        <label>{t('reports.catalog.reportKindLabel')}<select value={draft.report_kind} onChange={(event) => setDraft({ ...draft, report_kind: event.target.value as CatalogReportConfig['report_kind'] })}><option value="indicators">{t('reports.catalog.kindIndicators')}</option><option value="committee">{t('reports.catalog.kindCommittee')}</option></select></label>{draft.report_kind === 'committee' && <CommitteeEditor value={draft.committee} onChange={(committee) => setDraft({ ...draft, committee })} />}<section className="catalog-library-picker"><h3>{t('reports.catalog.libraryIndicators')}</h3><a href="/reports/indicators">{t('reports.catalog.configureIndicators')}</a>{library.length ? library.map((entry) => <label key={entry.id}><input type="checkbox" checked={draft.indicator_ids.includes(entry.id)} onChange={(event) => setDraft({ ...draft, indicator_ids: event.target.checked ? [...draft.indicator_ids, entry.id] : draft.indicator_ids.filter((id) => id !== entry.id) })} />{entry.definition.code} · {entry.definition.title} · {t('reports.catalog.goalPrefix', { goal: entry.definition.goal })}</label>) : <p>{t('reports.catalog.libraryEmpty')}</p>}</section><h3>{t('reports.catalog.ownIndicators')}</h3>{draft.indicators.map((item, index) => <fieldset key={index} className="catalog-indicator-edit"><legend>{t('reports.catalog.indicatorN', { n: index + 1 })}</legend><label>{t('reports.catalog.nameLabel')}<input value={item.title} onChange={(event) => changeIndicator(index, { title: event.target.value })} placeholder={t('reports.catalog.indicatorExample')} /></label><div className="catalog-form-grid"><label>{t('reports.catalog.sourceMode')}<select value={item.source_mode} onChange={(event) => changeIndicator(index, { source_mode: event.target.value as IndicatorDefinition['source_mode'], manual_actual: event.target.value === 'manual' ? (item.manual_actual ?? 0) : null })}><option value="automatic">{t('reports.catalog.sourceModeAutomatic')}</option><option value="manual">{t('reports.catalog.sourceModeManual')}</option></select></label>{item.source_mode === 'automatic' && !item.sources.length && <><label>{t('reports.catalog.formLabel')}<select value={item.template_id ?? ''} onChange={(event) => changeIndicator(index, { template_id: event.target.value, value_field: null, municipality_field: null })}><option value="">{t('reports.catalog.selectOption')}</option>{templates.map((template) => <option key={template.id} value={template.id}>{template.name}</option>)}</select></label><label>{t('reports.catalog.calculationLabel')}<select value={item.aggregation} onChange={(event) => changeIndicator(index, { aggregation: event.target.value as IndicatorDefinition['aggregation'] })}><option value="count">{t('reports.catalog.aggCount')}</option><option value="sum">{t('reports.catalog.aggSum')}</option><option value="average">{t('reports.catalog.aggAverage')}</option><option value="unique_count">{t('reports.catalog.aggUniqueCount')}</option></select></label><label>{t('reports.catalog.resultVariable')}<select value={item.value_field ?? ''} onChange={(event) => changeIndicator(index, { value_field: event.target.value || null })}><option value="">{item.aggregation === 'count' ? t('reports.catalog.eachResponse') : t('reports.catalog.selectVariable')}</option>{(fields[item.template_id ?? ''] ?? []).map((field) => <option key={field.name} value={field.name}>{field.label} ({field.name})</option>)}</select></label><label>{t('reports.catalog.breakdownLabel')}<select value={item.municipality_field ?? ''} onChange={(event) => changeIndicator(index, { municipality_field: event.target.value || null })}><option value="">{t('reports.catalog.noBreakdown')}</option>{(fields[item.template_id ?? ''] ?? []).map((field) => <option key={field.name} value={field.name}>{field.label} ({field.name})</option>)}</select></label></>}<label>{t('reports.catalog.goalLabel')}<input type="number" min="0" value={item.goal} onChange={(event) => changeIndicator(index, { goal: Number(event.target.value) })} /></label>{item.source_mode === 'manual' && <label>{t('reports.catalog.currentProgress')}<input type="number" min="0" value={item.manual_actual ?? 0} onChange={(event) => changeIndicator(index, { manual_actual: Number(event.target.value) })} /></label>}<label>{t('reports.catalog.unitLabel')}<input value={item.unit} maxLength={30} onChange={(event) => changeIndicator(index, { unit: event.target.value })} placeholder={t('reports.catalog.unitPlaceholder')} /></label><label>{t('reports.catalog.viewKindLabel')}<select value={item.view_kind} onChange={(event) => changeIndicator(index, { view_kind: event.target.value as IndicatorDefinition['view_kind'] })}><option value="progress">{t('reports.catalog.viewProgress')}</option><option value="table">{t('reports.catalog.viewTable')}</option><option value="bar">{t('reports.catalog.viewBar')}</option></select></label></div><IndicatorSourcesEditor value={item} templates={templates} fields={fields} onChange={(patch) => changeIndicator(index, patch)} />{(draft.indicators.length > 1 || draft.indicator_ids.length > 0) && <button type="button" className="catalog-remove" onClick={() => setDraft({ ...draft, indicators: draft.indicators.filter((_, itemIndex) => itemIndex !== index) })}>{t('reports.catalog.removeIndicator')}</button>}</fieldset>)}<div className="catalog-editor-actions"><button type="button" onClick={() => setDraft({ ...draft, indicators: [...draft.indicators, blankIndicator(templates[0]?.id)] })}>{t('reports.catalog.addIndicator')}</button><button type="button" onClick={() => void save()} disabled={saving || !draft.name.trim() || (!draft.indicators.length && !draft.indicator_ids.length) || draft.indicators.some((item) => !item.title.trim() || (item.source_mode === 'automatic' && (item.sources.length ? item.sources.some((row) => !row.template_id || (['union', 'intersection', 'all'].includes(item.combination) && !row.key_field)) : !item.template_id))) || (draft.report_kind === 'committee' && [...draft.committee.activities.map((row) => row.title), ...draft.committee.alerts.map((row) => row.title), ...draft.committee.budget.map((row) => row.component), ...draft.committee.previous_agreements.map((row) => row.title), ...draft.committee.new_agreements.map((row) => row.title)].some((title) => !title.trim()))}>{saving ? t('reports.catalog.saving') : t('reports.catalog.saveReport')}</button><button type="button" onClick={() => setEditing(false)}>{t('reports.catalog.cancel')}</button></div></div> : result ? <><div className="catalog-manage">{canEdit && <><button type="button" onClick={startEdit}>{t('reports.catalog.editIndicators')}</button><button type="button" onClick={() => void share()}>{t('reports.catalog.createPublicLink')}</button></>}</div>{result.report_kind === 'committee' ? <CommitteeReportView report={result} /> : <CatalogReportView report={result} />}{canEdit && <section className="catalog-sharing"><h3>{t('reports.catalog.publicLinks')}</h3><p>{t('reports.catalog.publicLinksDescription')}</p>{issuedUrl && <div className="catalog-issued"><input readOnly aria-label={t('reports.catalog.publicLinkAria')} value={issuedUrl} /><button type="button" onClick={() => void navigator.clipboard.writeText(issuedUrl)}>{t('reports.catalog.copyLink')}</button></div>}{links.map((link) => <div key={link.id} className="catalog-link-row"><span>{link.status} · {link.expires_at ? t('reports.catalog.expiresAt', { date: new Date(link.expires_at).toLocaleDateString() }) : t('reports.catalog.noExpiry')}</span>{link.status === 'active' && <button type="button" onClick={() => void revoke(link.id)}>{t('reports.catalog.revoke')}</button>}</div>)}</section>}</> : canEdit ? <ReportModels onPick={(model) => model === 'committee' ? startNew('committee') : model === 'blank' ? startNew() : startFromModel(model)} /> : <div className="reports-empty"><h3>{t('reports.catalog.selectOrCreate')}</h3><p>{t('reports.catalog.selectOrCreateDesc')}</p></div>}</section>
    </div>
  </main></AppShell>;
}

function ReportModels({ onPick }: { onPick: (model: 'progress' | 'territory' | 'committee' | 'blank') => void }) {
  const { t } = useI18n();
  const models = [
    { key: 'progress', icon: 'metric', title: 'reports.catalog.modelProgress', text: 'reports.catalog.modelProgressText' },
    { key: 'territory', icon: 'map', title: 'reports.catalog.modelTerritory', text: 'reports.catalog.modelTerritoryText' },
    { key: 'committee', icon: 'users', title: 'reports.catalog.modelCommittee', text: 'reports.catalog.modelCommitteeText' },
    { key: 'blank', icon: 'form', title: 'reports.catalog.modelBlank', text: 'reports.catalog.modelBlankText' },
  ] as const;
  return (
    <section className="report-models" aria-labelledby="report-models-title">
      <h3 id="report-models-title">{t('reports.catalog.modelsTitle')}</h3>
      <p>{t('reports.catalog.modelsIntro')}</p>
      <div className="report-models-grid">
        {models.map((model) => (
          <button type="button" key={model.key} className="report-model" onClick={() => onPick(model.key)}>
            <span className="report-model-icon" aria-hidden="true"><Icon name={model.icon} /></span>
            <strong>{t(model.title)}</strong>
            <span>{t(model.text)}</span>
            <em>{t('reports.catalog.modelUse')}</em>
          </button>
        ))}
      </div>
    </section>
  );
}
