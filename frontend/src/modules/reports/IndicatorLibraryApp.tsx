import { useEffect, useState } from 'react';
import { AppShell } from '../../components/AppShell';
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
      setRows(await listLibraryIndicators(projectId)); setSelectedId(saved.id); setDraft(saved.definition); setMessage('Indicador guardado. Los reportes asociados usarán su definición actual.');
    } catch (error) { setMessage(error instanceof Error ? error.message : 'No se pudo guardar.'); }
    finally { setBusy(false); }
  }

  async function previewFile() {
    if (!file) return;
    setBusy(true); setMessage('');
    try { const result = await previewIndicatorWorkbook(projectId, file); setPreview(result); setMessage(`${result.indicators.length} indicador(es) válidos, ${result.errors.length} error(es).`); }
    catch (error) { setMessage(error instanceof Error ? error.message : 'No se pudo validar el Excel.'); }
    finally { setBusy(false); }
  }

  async function applyFile() {
    if (!file || !preview || preview.errors.length) return;
    setBusy(true); setMessage('');
    try { const imported = await applyIndicatorWorkbook(projectId, file); setRows(await listLibraryIndicators(projectId)); setFile(null); setPreview(null); setMessage(`${imported.length} indicador(es) importados.`); }
    catch (error) { setMessage(error instanceof Error ? error.message : 'No se pudo importar.'); }
    finally { setBusy(false); }
  }

  return <AppShell title="Configuración de indicadores"><main className="reports-shell reports-studio report-catalog">
    <header className="reports-header"><div><h2>Configuración de indicadores</h2><p>Crea una sola definición por indicador y úsala en varios reportes. Las metas se editan aquí; el avance automático se calcula con los formularios asociados.</p></div><div className="reports-actions"><a href="/reports/catalog">← Reportes</a>{canEdit && <button type="button" onClick={() => { setSelectedId(''); setDraft(blank(templates[0]?.id)); }}>+ Nuevo indicador</button>}</div></header>
    {message && <p role="status" className="catalog-message">{message}</p>}
    {canEdit && <section className="catalog-editor indicator-import"><h3>Importar indicadores desde Excel</h3><button type="button" onClick={() => void downloadIndicatorWorkbookTemplate(projectId)}>⬇ Descargar plantilla</button><input type="file" accept=".xlsx" aria-label="Archivo de indicadores" onChange={(event) => { setFile(event.target.files?.[0] ?? null); setPreview(null); }} /><button type="button" disabled={!file || busy} onClick={() => void previewFile()}>Validar archivo</button>{preview && <div><strong>{preview.indicators.length} válidos · {preview.errors.length} errores</strong>{preview.errors.map((error) => <p key={error.row}>Fila {error.row}: {error.error}</p>)}<button type="button" disabled={busy || !!preview.errors.length || !preview.indicators.length} onClick={() => void applyFile()}>Importar indicadores validados</button></div>}</section>}
    <div className="catalog-layout"><aside className="catalog-list"><h3>Indicadores del proyecto</h3>{rows.map((row) => <button type="button" key={row.id} className={selectedId === row.id ? 'active' : ''} onClick={() => { setSelectedId(row.id); setDraft({ ...row.definition }); }}><strong>{row.definition.code} · {row.definition.title}</strong><small>Meta: {row.definition.goal.toLocaleString('es-CO')} {row.definition.unit} · {row.definition.source_mode === 'manual' ? 'Manual' : `${row.definition.sources.length || 1} formulario(s)`}</small></button>)}{!rows.length && <p>Aún no hay indicadores. Crea uno o importa un Excel.</p>}</aside>
      <section className="catalog-content">{draft ? <div className="catalog-editor"><h2>{selectedId ? 'Editar indicador' : 'Nuevo indicador'}</h2><label>Nombre<input value={draft.title} onChange={(event) => setDraft({ ...draft, title: event.target.value })} /></label><div className="catalog-form-grid"><label>Origen<select value={draft.source_mode} onChange={(event) => setDraft({ ...draft, source_mode: event.target.value as IndicatorDefinition['source_mode'], manual_actual: event.target.value === 'manual' ? draft.manual_actual ?? 0 : null })}><option value="automatic">Automático desde formularios</option><option value="manual">Avance manual</option></select></label><label>Meta<input type="number" min="0" value={draft.goal} onChange={(event) => setDraft({ ...draft, goal: Number(event.target.value) })} /></label><label>Unidad<input value={draft.unit} onChange={(event) => setDraft({ ...draft, unit: event.target.value })} /></label>{draft.source_mode === 'manual' && <label>Avance actual<input type="number" min="0" value={draft.manual_actual ?? 0} onChange={(event) => setDraft({ ...draft, manual_actual: Number(event.target.value) })} /></label>}</div>
        {draft.source_mode === 'automatic' && !draft.sources.length && <div className="catalog-form-grid"><label>Formulario<select value={draft.template_id ?? ''} onChange={(event) => setDraft({ ...draft, template_id: event.target.value || null, value_field: null })}><option value="">Seleccionar</option>{templates.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label>Operación<select value={draft.aggregation} onChange={(event) => setDraft({ ...draft, aggregation: event.target.value as IndicatorDefinition['aggregation'] })}><option value="count">Contar respuestas</option><option value="unique_count">Conteo único de variable</option><option value="sum">Sumar variable</option><option value="average">Promediar variable</option></select></label><label>Variable<select value={draft.value_field ?? ''} onChange={(event) => setDraft({ ...draft, value_field: event.target.value || null })}><option value="">{draft.aggregation === 'count' ? 'Cada respuesta' : 'Seleccionar variable'}</option>{(fields[draft.template_id ?? ''] ?? []).map((field) => <option key={field.name} value={field.name}>{field.label} ({field.name})</option>)}</select></label></div>}
        <IndicatorSourcesEditor value={draft} templates={templates} fields={fields} onChange={(patch) => setDraft({ ...draft, ...patch })} />
        {canEdit && <div className="catalog-editor-actions"><button type="button" disabled={busy || !draft.code.trim() || !draft.title.trim() || (draft.source_mode === 'automatic' && (draft.sources.length ? draft.sources.some((source) => !source.template_id || (['union', 'intersection', 'all'].includes(draft.combination) && !source.key_field)) : !draft.template_id))} onClick={() => void save()}>{busy ? 'Guardando…' : 'Guardar indicador'}</button></div>}</div> : <div className="reports-empty"><h3>Selecciona o crea un indicador</h3><p>Los reportes usarán esta configuración compartida y mostrarán el avance actualizado.</p></div>}</section>
    </div>
  </main></AppShell>;
}
