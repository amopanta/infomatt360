import { useEffect, useMemo, useState } from 'react';
import { AppShell } from '../../components/AppShell';
import { authorizationHeader, PROJECT_KEY } from '../auth/session';
import { fetchProjectTemplates } from '../records/api';
import { RecordTable } from '../records/RecordsApp';
import type { TemplateSummary } from '../records/api';
import type { RuntimeTemplate } from '../runtime/types';
import { createPublicLink, fetchPublicLinks } from '../admin/publicLinksApi';
import type { PublicFormLink } from '../admin/publicLinksApi';
import { duplicateTemplate, fetchTemplateDetail, setTemplateSchedule, setTemplateStatus, updateTemplateProperties } from './api';
import { CollectionPanel } from './CollectionPanel';
import { ParticipantSourcePanel } from './ParticipantSourcePanel';
import { BulkPullPanel, FormLookupPanel } from './FormLookupPanel';
import { exportXlsform, listFormVersions } from '../admin/xlsformApi';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';
type DetailTab = 'resumen' | 'formulario' | 'datos' | 'configuracion';

function displayDate(value?: string | null) {
  if (!value) return '—';
  const zoned = /(?:Z|[+-]\d\d:\d\d)$/.test(value) ? value : `${value}Z`;
  return new Date(zoned).toLocaleString('es-CO', { day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function publicationLabel(template: TemplateSummary) {
  const labels: Record<string, string> = {
    accepting: 'Recibiendo respuestas', scheduled: 'Programado', closed: 'Finalizado',
    paused: 'Respuestas detenidas', archived: 'Archivado', draft: 'Borrador',
  };
  return labels[template.availability || template.status] || template.status;
}

function statusClass(template: TemplateSummary) {
  return template.availability || template.status;
}

function localInputDate(value?: string | null) {
  if (!value) return '';
  const zoned = /(?:Z|[+-]\d\d:\d\d)$/.test(value) ? value : `${value}Z`;
  const date = new Date(zoned);
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}

async function fetchRuntime(templateId: string): Promise<RuntimeTemplate> {
  const response = await fetch(`${API_BASE_URL}/runtime/template/${templateId}`, { headers: authorizationHeader() });
  if (!response.ok) throw new Error('No fue posible cargar las preguntas del formulario.');
  return response.json();
}

export function FormsApp() {
  const templateId = window.location.pathname.match(/^\/builder\/form\/([^/]+)$/)?.[1];
  return templateId ? <FormDetail templateId={templateId} /> : <FormList />;
}

function FormList() {
  const view = window.location.pathname.split('/')[2] || 'all';
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';
  const [templates, setTemplates] = useState<TemplateSummary[]>([]);
  const [filter, setFilter] = useState('');
  const [message, setMessage] = useState('Cargando formularios…');

  useEffect(() => {
    if (!projectId) { setMessage('Selecciona un proyecto para ver sus formularios.'); return; }
    fetchProjectTemplates(projectId)
      .then((rows) => { setTemplates(rows); setMessage(''); })
      .catch((error: Error) => setMessage(error.message));
  }, [projectId]);

  const visible = useMemo(() => templates.filter((template) => {
    const inView = view === 'drafts' ? template.status === 'draft' : view === 'active' ? ['published', 'paused'].includes(template.status) : view === 'archived' ? template.status === 'archived' : true;
    return inView && template.name.toLowerCase().includes(filter.toLowerCase());
  }), [templates, filter, view]);
  const active = templates.filter((template) => ['published', 'paused'].includes(template.status)).length;
  const title = view === 'drafts' ? 'En construcción' : view === 'active' ? 'Formularios activos' : view === 'archived' ? 'Formularios archivados' : 'Todos los formularios';
  return <AppShell title="Formularios">
    <main className="forms-home">
      <header className="forms-home-head">
        <div><h1>{title}</h1><p>Construye, publica, programa y consulta los envíos de cada formulario.</p></div>
        <a className="forms-primary-link" href="/builder/new">+ Nuevo formulario</a>
      </header>
      <div className="forms-overview"><strong>{templates.length} formularios</strong><span>{active} activos o detenidos</span><span>{templates.filter((template) => template.status === 'draft').length} borradores</span><span>{templates.filter((template) => template.status === 'archived').length} archivados</span></div>
      <div className="forms-toolbar"><label>Buscar formulario<input value={filter} onChange={(event) => setFilter(event.target.value)} placeholder="Nombre del formulario" /></label></div>
      {message ? <p role="status" className="forms-feedback">{message}</p> : null}
      {!message && !templates.length ? <section className="forms-empty"><h2>Aún no hay formularios visuales</h2><p>El formulario de prueba del módulo clásico no aparece aquí. Crea uno en el constructor y publícalo cuando esté listo.</p><a className="forms-primary-link" href="/builder/new">Crear primer formulario</a></section> : null}
      {!!visible.length && <div className="forms-table-wrap"><table className="forms-table"><thead><tr><th>Nombre del formulario</th><th>Estado</th><th>Propietario</th><th>Última edición</th><th>Inicio</th><th>Fin</th><th>Envíos</th></tr></thead><tbody>
        {visible.map((template) => <tr key={template.id}><td><a className="forms-name" href={`/builder/form/${template.id}`}>{template.name}</a><small>{template.description || 'Sin descripción'}</small></td><td><span className={`forms-status ${statusClass(template)}`}>{publicationLabel(template)}</span></td><td>{template.owner_name || '—'}</td><td>{displayDate(template.updated_at || template.created_at)}</td><td>{displayDate(template.starts_at)}</td><td>{displayDate(template.ends_at)}</td><td><span className="forms-count">{template.submissions_count ?? 0}</span></td></tr>)}
      </tbody></table></div>}
      {!!templates.length && <BulkPullPanel projectId={projectId} forms={templates} />}
      {!!templates.length && !visible.length && <p className="forms-feedback">No hay formularios en esta sección que coincidan con la búsqueda.</p>}
    </main>
  </AppShell>;
}

function FormDetail({ templateId }: { templateId: string }) {
  const [template, setTemplate] = useState<TemplateSummary | null>(null);
  const [runtime, setRuntime] = useState<RuntimeTemplate | null>(null);
  const [links, setLinks] = useState<PublicFormLink[]>([]);
  const [newPublicUrl, setNewPublicUrl] = useState('');
  const [tab, setTab] = useState<DetailTab>('resumen');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('Cargando formulario…');
  const [startsAt, setStartsAt] = useState('');
  const [endsAt, setEndsAt] = useState('');
  const [formName, setFormName] = useState('');
  const [formDescription, setFormDescription] = useState('');
  const [versionCount, setVersionCount] = useState(0);
  const [pullCount, setPullCount] = useState(0);

  useEffect(() => {
    setMessage('Cargando formulario…');
    Promise.all([fetchTemplateDetail(templateId), fetchRuntime(templateId), fetchPublicLinks(templateId)])
      .then(([detail, layout, publicLinks]) => { setTemplate(detail); setRuntime(layout); setLinks(publicLinks); setStartsAt(localInputDate(detail.starts_at)); setEndsAt(localInputDate(detail.ends_at)); setFormName(detail.name); setFormDescription(detail.description || ''); setMessage(''); })
      .catch((error: Error) => setMessage(error.message));
    void listFormVersions(templateId).then((versions) => setVersionCount(versions.length)).catch(() => setVersionCount(0));
    void fetch(`${API_BASE_URL}/form-lookups/templates/${templateId}`, { headers: authorizationHeader() }).then((response) => response.ok ? response.json() : []).then((items: unknown[]) => setPullCount(items.length)).catch(() => setPullCount(0));
  }, [templateId]);

  const questions = runtime?.pages.flatMap((page) => page.sections.flatMap((section) => section.rows.flatMap((row) => row.columns.flatMap((column) => column.components)))) ?? [];

  async function saveProperties() {
    if (!template) return;
    if (!formName.trim()) { setMessage('El nombre del formulario es obligatorio.'); return; }
    setBusy(true);
    setMessage('');
    try {
      const updated = await updateTemplateProperties(template.id, { name: formName.trim(), description: formDescription, themeJson: template.theme_json || null });
      setTemplate(updated);
      setMessage('Nombre y descripción guardados.');
    } catch (error) { setMessage(error instanceof Error ? error.message : 'No fue posible guardar el nombre.'); }
    finally { setBusy(false); }
  }

  async function changeStatus(next: 'draft' | 'published' | 'paused' | 'archived') {
    if (!template) return;
    setBusy(true);
    setMessage('');
    try {
      const updated = await setTemplateStatus(template.id, next);
      setTemplate(updated);
      const messages = { draft: 'Formulario restaurado como borrador.', published: 'Formulario publicado. La ventana de fechas controla cuándo recibe respuestas.', paused: 'Recepción de respuestas detenida en todos los canales.', archived: 'Formulario archivado. Los datos existentes se conservan.' };
      setMessage(messages[next]);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible cambiar el estado.');
    } finally { setBusy(false); }
  }

  async function saveSchedule() {
    if (!template) return;
    setBusy(true);
    setMessage('');
    try {
      const start = startsAt ? new Date(startsAt).toISOString() : null;
      const end = endsAt ? new Date(endsAt).toISOString() : null;
      if (start && end && start >= end) throw new Error('La fecha de finalización debe ser posterior al inicio.');
      const updated = await setTemplateSchedule(template.id, start, end);
      setTemplate(updated);
      setMessage('Ventana de recepción guardada.');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible guardar las fechas.');
    } finally { setBusy(false); }
  }

  async function makeLink() {
    setBusy(true);
    setMessage('');
    try {
      const issued = await createPublicLink({ templateId });
      setNewPublicUrl(`${window.location.origin}/public-form/${issued.token}`);
      setLinks(await fetchPublicLinks(templateId));
      setMessage('Enlace público creado. Cópialo ahora; el token completo se muestra una sola vez.');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible crear el enlace.');
    } finally { setBusy(false); }
  }

  async function copyForm() {
    if (!template) return;
    setBusy(true); setMessage('');
    try { const copy = await duplicateTemplate(template.id); window.location.href = `/builder/form/${copy.id}`; }
    catch (error) { setMessage(error instanceof Error ? error.message : 'No fue posible duplicar el formulario.'); setBusy(false); }
  }

  return <AppShell title="Formulario"><main className="forms-detail">
    <a className="forms-back" href="/builder">← Todos los formularios</a>
    {template && <><header className="forms-detail-head"><div><h1>{template.name}</h1><p>{template.description || 'Sin descripción'}</p></div><span className={`forms-status ${statusClass(template)}`}>{publicationLabel(template)}</span></header>
    <nav className="forms-tabs" aria-label="Secciones del formulario">{(['resumen', 'formulario', 'datos', 'configuracion'] as DetailTab[]).map((item) => <button type="button" key={item} className={tab === item ? 'active' : ''} onClick={() => setTab(item)}>{item === 'configuracion' ? 'Configuración' : item.charAt(0).toUpperCase() + item.slice(1)}</button>)}</nav>
    {tab === 'resumen' && <><section className="forms-detail-panel"><h2>Centro de administración</h2><div className="forms-admin-actions"><a href={`/builder/edit/${template.id}`}>Editar</a><a href={`/admin/xlsform?replace=${template.id}`}>Reemplazar</a><a href={`/runtime/${template.id}?preview=1`}>Vista previa</a><button type="button" disabled={busy} onClick={() => void copyForm()}>Duplicar</button><a href={`/admin/xlsform?replace=${template.id}`}>Versiones</a><a href={`/records/${template.id}`}>Registros y respuestas</a><button type="button" onClick={() => void exportXlsform(template.id, template.name).catch((error: Error) => setMessage(error.message))}>Descargar formulario</button><button type="button" onClick={() => setTab('configuracion')}>Grupos Pull y participantes</button></div></section><div className="forms-detail-grid"><section className="forms-detail-panel"><h2>Información del formulario</h2><p>{template.description || 'Agrega una descripción para orientar a tu equipo.'}</p><dl className="forms-facts"><div><dt>Estado</dt><dd><span className={`forms-status ${statusClass(template)}`}>{publicationLabel(template)}</span></dd></div><div><dt>Preguntas</dt><dd>{questions.length}</dd></div><div><dt>Versiones</dt><dd>{versionCount}</dd></div><div><dt>Grupos Pull</dt><dd>{pullCount}</dd></div><div><dt>Propietario</dt><dd>{template.owner_name || '—'}</dd></div><div><dt>Última edición</dt><dd>{displayDate(template.updated_at || template.created_at)}</dd></div><div><dt>Inicio de respuestas</dt><dd>{displayDate(template.starts_at)}</dd></div><div><dt>Fin de respuestas</dt><dd>{displayDate(template.ends_at)}</dd></div><div><dt>Envíos</dt><dd>{template.submissions_count ?? 0}</dd></div><div><dt>Participantes</dt><dd>{template.participant_source?.mode === 'pull' ? `Grupo Pull: ${template.participant_source.pull_name}` : template.participant_source?.mode || 'Todos'}</dd></div></dl></section><section className="forms-detail-panel"><h2>Control de recepción</h2><p>{template.accepting_responses ? 'El formulario está recibiendo respuestas.' : `Estado actual: ${publicationLabel(template).toLowerCase()}.`}</p><button type="button" onClick={() => setTab('configuracion')}>Configurar publicación y fechas</button></section></div></>}
    {tab === 'formulario' && <section className="forms-detail-panel"><div className="forms-panel-head"><div><h2>Versión actual del formulario</h2><p>{questions.length} preguntas en {runtime?.pages.length ?? 0} página(s). Última edición: {displayDate(template.updated_at)}.</p></div><div className="forms-editor-links"><a href={`/builder/edit/${template.id}`} title="Editar en el constructor">✎ Editar en el constructor</a><a href={`/runtime/${template.id}?preview=1`} title="Vista previa del formulario">◉ Vista previa</a><a href={`/admin/xlsform?replace=${template.id}`} title="Validar y reemplazar con XLSForm">⇄ Reemplazar XLSForm</a></div></div>{runtime?.pages.map((page) => <div className="forms-page" key={page.id}><h3>{page.title}</h3>{page.sections.map((section) => <div key={section.id}><h4>{section.title}</h4><ol>{section.rows.flatMap((row) => row.columns.flatMap((column) => column.components)).map((component) => <li key={component.id}>{component.label}<small>{component.type}</small></li>)}</ol></div>)}</div>)}{!questions.length && <p>Este formulario aún no tiene preguntas.</p>}<CollectionPanel template={template} onIssued={() => void fetchPublicLinks(templateId).then(setLinks).catch(() => undefined)} /></section>}
    {tab === 'datos' && <section className="forms-detail-panel forms-data-panel"><div className="forms-data-toolbar"><div><h2>Respuestas del formulario</h2><p>{template.submissions_count ?? 0} respuestas recibidas. La grilla muestra todos los campos capturados.</p></div><a className="forms-primary-link" href={`/reports/form/${template.id}`}>Ver informe individual</a></div><RecordTable templateId={template.id} embedded /></section>}
    {tab === 'configuracion' && <section className="forms-detail-panel"><h2>Propiedades del formulario</h2><div className="forms-properties"><label>Nombre del formulario<input value={formName} maxLength={180} onChange={(event) => setFormName(event.target.value)} /></label><label>Descripción<textarea rows={3} value={formDescription} onChange={(event) => setFormDescription(event.target.value)} /></label><button type="button" disabled={busy || !formName.trim()} onClick={() => void saveProperties()}>Guardar nombre y descripción</button></div><h2>Publicación y respuestas</h2><p>Publicar habilita la captura durante las fechas indicadas. Detener respuestas la pausa de inmediato; archivar conserva los datos y retira el formulario de los activos.</p><div className="forms-actions">{template.status === 'draft' && <button type="button" disabled={busy} onClick={() => void changeStatus('published')}>Publicar formulario</button>}{template.status === 'published' && <button type="button" disabled={busy} onClick={() => void changeStatus('paused')}>Detener respuestas</button>}{template.status === 'paused' && <button type="button" disabled={busy} onClick={() => void changeStatus('published')}>Reanudar respuestas</button>}{template.status !== 'archived' && <button type="button" className="forms-archive-button" disabled={busy} onClick={() => void changeStatus('archived')}>Archivar formulario</button>}{template.status === 'archived' && <button type="button" disabled={busy} onClick={() => void changeStatus('draft')}>Restaurar como borrador</button>}</div><div className="forms-schedule"><h3>Ventana de recepción</h3><p>Deja una fecha vacía si no quieres limitar ese extremo. Las fechas se interpretan en tu zona horaria.</p><div className="forms-schedule-fields"><label>Fecha y hora de inicio<input type="datetime-local" value={startsAt} onChange={(event) => setStartsAt(event.target.value)} /></label><label>Fecha y hora de finalización<input type="datetime-local" value={endsAt} onChange={(event) => setEndsAt(event.target.value)} /></label></div><button type="button" disabled={busy || template.status === 'archived'} onClick={() => void saveSchedule()}>Guardar fechas</button></div><div className="forms-public-links"><h3>Enlaces públicos</h3><p>{links.length} enlace(s) generados. Sólo admiten respuestas si el formulario está publicado y dentro de la ventana de fechas.</p><button type="button" disabled={busy || template.status !== 'published' || template.availability === 'closed'} onClick={() => void makeLink()}>Generar enlace público</button>{newPublicUrl && <label>Nuevo enlace — cópialo ahora<input readOnly value={newPublicUrl} onFocus={(event) => event.target.select()} /></label>}<a href={`/admin/public-links?template=${template.id}`}>Administrar enlaces y vencimientos</a></div></section>}
    {tab === 'configuracion' && <section className="forms-detail-panel"><ParticipantSourcePanel template={template} onUpdate={setTemplate} /></section>}
    {tab === 'configuracion' && <section className="forms-detail-panel"><FormLookupPanel templateId={template.id} /></section>}
    </>}
    {message && <p role="status" className="forms-feedback">{message}</p>}
  </main></AppShell>;
}
