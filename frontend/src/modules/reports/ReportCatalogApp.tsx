import { useEffect, useState } from 'react';
import { AppShell } from '../../components/AppShell';
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
    catch (error) { setMessage(error instanceof Error ? error.message : 'No fue posible abrir el reporte.'); }
  }

  function startNew(kind: CatalogReportConfig['report_kind'] = 'indicators') {
    setSelectedId(''); setResult(null); setLinks([]); setIssuedUrl(''); setMessage('');
    setDraft({ project_id: projectId, name: '', description: '', report_kind: kind, committee: blankCommittee(), starts_at: null, ends_at: null, indicators: library.length ? [] : [blankIndicator(templates[0]?.id)], indicator_ids: [] });
    setEditing(true);
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
    } catch (error) { setMessage(error instanceof Error ? error.message : 'No fue posible guardar.'); }
    finally { setSaving(false); }
  }

  async function share() {
    if (!selectedId) return;
    setMessage('');
    try {
      const issued = await issueReportLink(selectedId);
      setIssuedUrl(`${window.location.origin}/public-report/${issued.token}`);
      setLinks(await listReportLinks(selectedId));
    } catch (error) { setMessage(error instanceof Error ? error.message : 'No fue posible crear el enlace.'); }
  }

  async function revoke(linkId: string) {
    if (!selectedId) return;
    try { await revokeReportLink(selectedId, linkId); setLinks(await listReportLinks(selectedId)); setIssuedUrl(''); }
    catch (error) { setMessage(error instanceof Error ? error.message : 'No fue posible revocar.'); }
  }

  return <AppShell title="Reportes"><main className="reports-shell reports-studio report-catalog">
    <header className="reports-header"><div><h2>Reportes personalizados</h2><p>Vincula formularios, variables, metas y municipios.</p></div><div className="reports-actions"><a href="/reports">← Tablero</a>{canEdit && <button type="button" onClick={() => startNew()}>+ Crear reporte</button>}{canEdit && <button type="button" onClick={() => startNew('committee')}>+ Informe de comité</button>}</div></header>
    {message && <p role="alert" className="catalog-message">{message}</p>}
    <div className="catalog-layout"><aside className="catalog-list"><h3>Mis reportes</h3>{reports.length ? reports.map((item) => <button type="button" className={selectedId === item.id ? 'active' : ''} key={item.id} onClick={() => void open(item.id)}><strong>{item.name}</strong><small>{item.report_kind === 'committee' ? 'Informe de comité · ' : ''}{item.indicators.length + (item.indicator_ids?.length ?? 0)} indicador(es)</small></button>) : <p>Aún no hay reportes. Crea uno para relacionar tus formularios con una meta.</p>}</aside>
      <section className="catalog-content">{editing && draft ? <div className="catalog-editor"><h2>{selectedId ? 'Editar reporte' : 'Nuevo reporte'}</h2><label>Nombre del reporte<input value={draft.name} maxLength={180} onChange={(event) => setDraft({ ...draft, name: event.target.value })} /></label><label>Descripción<textarea value={draft.description} maxLength={1000} onChange={(event) => setDraft({ ...draft, description: event.target.value })} /></label><div className="catalog-date-grid"><label>Desde<input type="datetime-local" value={draft.starts_at?.slice(0, 16) ?? ''} onChange={(event) => setDraft({ ...draft, starts_at: event.target.value || null })} /></label><label>Hasta<input type="datetime-local" value={draft.ends_at?.slice(0, 16) ?? ''} onChange={(event) => setDraft({ ...draft, ends_at: event.target.value || null })} /></label></div>
        <label>Tipo de informe<select value={draft.report_kind} onChange={(event) => setDraft({ ...draft, report_kind: event.target.value as CatalogReportConfig['report_kind'] })}><option value="indicators">Indicadores y metas</option><option value="committee">Seguimiento de comité</option></select></label>{draft.report_kind === 'committee' && <CommitteeEditor value={draft.committee} onChange={(committee) => setDraft({ ...draft, committee })} />}<section className="catalog-library-picker"><h3>Indicadores de la biblioteca</h3><a href="/reports/indicators">Configurar indicadores</a>{library.length ? library.map((entry) => <label key={entry.id}><input type="checkbox" checked={draft.indicator_ids.includes(entry.id)} onChange={(event) => setDraft({ ...draft, indicator_ids: event.target.checked ? [...draft.indicator_ids, entry.id] : draft.indicator_ids.filter((id) => id !== entry.id) })} />{entry.definition.code} · {entry.definition.title} · Meta {entry.definition.goal}</label>) : <p>La biblioteca está vacía. Puedes configurar indicadores una vez y reutilizarlos en varios reportes.</p>}</section><h3>Indicadores propios de este reporte</h3>{draft.indicators.map((item, index) => <fieldset key={index} className="catalog-indicator-edit"><legend>Indicador {index + 1}</legend><label>Nombre<input value={item.title} onChange={(event) => changeIndicator(index, { title: event.target.value })} placeholder="Ej. Beneficiarios alcanzados" /></label><div className="catalog-form-grid"><label>Origen del indicador<select value={item.source_mode} onChange={(event) => changeIndicator(index, { source_mode: event.target.value as IndicatorDefinition['source_mode'], manual_actual: event.target.value === 'manual' ? (item.manual_actual ?? 0) : null })}><option value="automatic">Automático desde formulario</option><option value="manual">Avance manual</option></select></label>{item.source_mode === 'automatic' && !item.sources.length && <><label>Formulario<select value={item.template_id ?? ''} onChange={(event) => changeIndicator(index, { template_id: event.target.value, value_field: null, municipality_field: null })}><option value="">Seleccionar</option>{templates.map((template) => <option key={template.id} value={template.id}>{template.name}</option>)}</select></label><label>Cálculo<select value={item.aggregation} onChange={(event) => changeIndicator(index, { aggregation: event.target.value as IndicatorDefinition['aggregation'] })}><option value="count">Contar respuestas o valores</option><option value="sum">Sumar variable numérica</option><option value="average">Promediar variable numérica</option><option value="unique_count">Contar valores únicos</option></select></label><label>Variable de resultado<select value={item.value_field ?? ''} onChange={(event) => changeIndicator(index, { value_field: event.target.value || null })}><option value="">{item.aggregation === 'count' ? 'Cada respuesta' : 'Seleccionar variable'}</option>{(fields[item.template_id ?? ''] ?? []).map((field) => <option key={field.name} value={field.name}>{field.label} ({field.name})</option>)}</select></label><label>Desglosar por municipio u otra variable<select value={item.municipality_field ?? ''} onChange={(event) => changeIndicator(index, { municipality_field: event.target.value || null })}><option value="">Sin desglose</option>{(fields[item.template_id ?? ''] ?? []).map((field) => <option key={field.name} value={field.name}>{field.label} ({field.name})</option>)}</select></label></>}<label>Meta<input type="number" min="0" value={item.goal} onChange={(event) => changeIndicator(index, { goal: Number(event.target.value) })} /></label>{item.source_mode === 'manual' && <label>Avance actual<input type="number" min="0" value={item.manual_actual ?? 0} onChange={(event) => changeIndicator(index, { manual_actual: Number(event.target.value) })} /></label>}<label>Unidad<input value={item.unit} maxLength={30} onChange={(event) => changeIndicator(index, { unit: event.target.value })} placeholder="personas, talleres..." /></label><label>Visualización<select value={item.view_kind} onChange={(event) => changeIndicator(index, { view_kind: event.target.value as IndicatorDefinition['view_kind'] })}><option value="progress">Avance de meta</option><option value="table">Tabla por categoría</option><option value="bar">Barras por categoría</option></select></label></div><IndicatorSourcesEditor value={item} templates={templates} fields={fields} onChange={(patch) => changeIndicator(index, patch)} />{(draft.indicators.length > 1 || draft.indicator_ids.length > 0) && <button type="button" className="catalog-remove" onClick={() => setDraft({ ...draft, indicators: draft.indicators.filter((_, itemIndex) => itemIndex !== index) })}>Quitar indicador</button>}</fieldset>)}<div className="catalog-editor-actions"><button type="button" onClick={() => setDraft({ ...draft, indicators: [...draft.indicators, blankIndicator(templates[0]?.id)] })}>+ Agregar indicador</button><button type="button" onClick={() => void save()} disabled={saving || !draft.name.trim() || (!draft.indicators.length && !draft.indicator_ids.length) || draft.indicators.some((item) => !item.title.trim() || (item.source_mode === 'automatic' && (item.sources.length ? item.sources.some((row) => !row.template_id || (['union', 'intersection', 'all'].includes(item.combination) && !row.key_field)) : !item.template_id))) || (draft.report_kind === 'committee' && [...draft.committee.activities.map((row) => row.title), ...draft.committee.alerts.map((row) => row.title), ...draft.committee.budget.map((row) => row.component), ...draft.committee.previous_agreements.map((row) => row.title), ...draft.committee.new_agreements.map((row) => row.title)].some((title) => !title.trim()))}>{saving ? 'Guardando…' : 'Guardar reporte'}</button><button type="button" onClick={() => setEditing(false)}>Cancelar</button></div></div> : result ? <><div className="catalog-manage">{canEdit && <><button type="button" onClick={startEdit}>Editar indicadores</button><button type="button" onClick={() => void share()}>Crear enlace público</button></>}</div>{result.report_kind === 'committee' ? <CommitteeReportView report={result} /> : <CatalogReportView report={result} />}{canEdit && <section className="catalog-sharing"><h3>Enlaces públicos</h3><p>Los enlaces son de solo lectura, vencen en 30 días y se pueden revocar. Muestran resultados agregados.</p>{issuedUrl && <div className="catalog-issued"><input readOnly aria-label="Enlace público recién creado" value={issuedUrl} /><button type="button" onClick={() => void navigator.clipboard.writeText(issuedUrl)}>Copiar enlace</button></div>}{links.map((link) => <div key={link.id} className="catalog-link-row"><span>{link.status} · {link.expires_at ? `vence ${new Date(link.expires_at).toLocaleDateString()}` : 'sin fecha'}</span>{link.status === 'active' && <button type="button" onClick={() => void revoke(link.id)}>Revocar</button>}</div>)}</section>}</> : <div className="reports-empty"><h3>Selecciona o crea un reporte</h3><p>Cada indicador puede usar una variable de un formulario, una meta y un desglose por municipio u otra categoría.</p></div>}</section>
    </div>
  </main></AppShell>;
}
