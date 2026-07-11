import { useEffect, useState } from 'react';

import { AppShell } from '../../components/AppShell';
import { PROJECT_KEY } from '../auth/session';
import { createMap, createSource, fetchJobs, fetchMaps, fetchSources } from './donorSyncApi';
import type { IntegrationJob, IntegrationMap, IntegrationSource } from './donorSyncApi';

type Tab = 'sources' | 'maps' | 'jobs';

function jobStatusLabel(status: string) {
  const labels: Record<string, string> = { sent: 'Enviado', failed: 'Fallido', pending: 'Pendiente' };
  return labels[status] ?? status;
}

export function DonorSyncApp() {
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';
  const [tab, setTab] = useState<Tab>('sources');
  const [message, setMessage] = useState('');

  const [sources, setSources] = useState<IntegrationSource[]>([]);
  const [selectedSourceId, setSelectedSourceId] = useState('');
  const [newSourceName, setNewSourceName] = useState('');
  const [newSourceType, setNewSourceType] = useState('activityinfo');
  const [newSourceUrl, setNewSourceUrl] = useState('');
  const [newSourceCredentials, setNewSourceCredentials] = useState('');

  const [maps, setMaps] = useState<IntegrationMap[]>([]);
  const [newMapTemplateId, setNewMapTemplateId] = useState('');
  const [newMapName, setNewMapName] = useState('');
  const [newMapTargetTable, setNewMapTargetTable] = useState('');
  const [newMapFieldsJson, setNewMapFieldsJson] = useState('{\n  "campo_del_formulario": "columna_destino"\n}');

  const [jobs, setJobs] = useState<IntegrationJob[]>([]);

  async function loadSources() {
    try {
      const rows = await fetchSources(projectId);
      setSources(rows);
      if (!selectedSourceId && rows[0]) setSelectedSourceId(rows[0].id);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible cargar las fuentes.');
    }
  }

  async function submitNewSource() {
    try {
      const created = await createSource({
        projectId, name: newSourceName, sourceType: newSourceType,
        baseUrl: newSourceUrl, credentials: newSourceCredentials, configJson: '',
      });
      setSources((current) => [...current, created]);
      setSelectedSourceId(created.id);
      setNewSourceName('');
      setNewSourceUrl('');
      setNewSourceCredentials('');
      setMessage('Fuente de integracion creada.');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible crear la fuente.');
    }
  }

  async function loadMaps() {
    if (!selectedSourceId) return;
    try {
      setMaps(await fetchMaps(selectedSourceId));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible cargar los mapeos.');
    }
  }

  async function submitNewMap() {
    try {
      const created = await createMap({
        sourceId: selectedSourceId, templateId: newMapTemplateId, name: newMapName,
        targetTable: newMapTargetTable, fieldsJson: newMapFieldsJson,
      });
      setMaps((current) => [...current, created]);
      setNewMapTemplateId('');
      setNewMapName('');
      setNewMapTargetTable('');
      setMessage('Mapeo creado.');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible crear el mapeo.');
    }
  }

  async function loadJobs() {
    if (!selectedSourceId) return;
    try {
      setJobs(await fetchJobs(selectedSourceId));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible cargar el historial de envios.');
    }
  }

  useEffect(() => { void loadSources(); }, [projectId]);
  useEffect(() => {
    if (tab === 'maps') void loadMaps();
    if (tab === 'jobs') void loadJobs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, selectedSourceId]);

  const selectedSource = sources.find((source) => source.id === selectedSourceId) ?? null;

  return (
    <AppShell title="Interoperabilidad de donantes">
      <main className="ds-shell">
        <nav className="erp-tabs">
          <button className={tab === 'sources' ? 'active' : undefined} onClick={() => setTab('sources')}>Fuentes</button>
          <button className={tab === 'maps' ? 'active' : undefined} onClick={() => setTab('maps')}>Mapeos de campos</button>
          <button className={tab === 'jobs' ? 'active' : undefined} onClick={() => setTab('jobs')}>Historial de envios</button>
        </nav>
        {message ? <p role="status" className="erp-message">{message}</p> : null}

        {tab === 'sources' ? (
          <section className="ds-sources">
            <div className="ds-source-create">
              <h2>Nueva fuente (ActivityInfo, TolaData u otra)</h2>
              <p>Conector generico configurable: URL base + credenciales. Ver docs/86 sobre por que no es un cliente especifico de una sola plataforma.</p>
              <label>Nombre<input value={newSourceName} onChange={(event) => setNewSourceName(event.target.value)} placeholder="ActivityInfo produccion" /></label>
              <label>
                Tipo (informativo)
                <select value={newSourceType} onChange={(event) => setNewSourceType(event.target.value)}>
                  <option value="activityinfo">ActivityInfo</option>
                  <option value="toladata">TolaData</option>
                  <option value="other">Otro</option>
                </select>
              </label>
              <label>URL base (endpoint que recibe el envio)<input value={newSourceUrl} onChange={(event) => setNewSourceUrl(event.target.value)} placeholder="https://api.donante.example/records" /></label>
              <label>Credenciales (API key/token, se cifran al guardar)<input value={newSourceCredentials} onChange={(event) => setNewSourceCredentials(event.target.value)} type="password" placeholder="opcional" /></label>
              <button className="primary" disabled={!newSourceName.trim() || !newSourceUrl.trim()} onClick={() => void submitNewSource()}>Crear fuente</button>
            </div>
            <div className="ds-source-list">
              <h2>Fuentes del proyecto</h2>
              {sources.length ? sources.map((source) => (
                <article className={selectedSourceId === source.id ? 'ds-source-card active' : 'ds-source-card'} key={source.id}>
                  <button onClick={() => setSelectedSourceId(source.id)}>
                    <strong>{source.name}</strong>
                    <span>{source.source_type} · {source.status}</span>
                    <small>{source.base_url ?? 'sin URL configurada'}</small>
                    <small>{source.has_credentials ? 'Con credenciales' : 'Sin credenciales'}</small>
                  </button>
                </article>
              )) : <p>Aun no hay fuentes de integracion en este proyecto.</p>}
            </div>
          </section>
        ) : null}

        {tab === 'maps' ? (
          <section className="ds-maps">
            {!selectedSource ? <p>Selecciona o crea una fuente primero en la pestaña "Fuentes".</p> : (
              <>
                <div className="ds-map-create">
                  <h2>Nuevo mapeo para "{selectedSource.name}"</h2>
                  <p>Al aprobarse un registro de la plantilla indicada, se envia el payload mapeado hacia esta fuente.</p>
                  <label>ID de la plantilla (Builder)<input value={newMapTemplateId} onChange={(event) => setNewMapTemplateId(event.target.value)} placeholder="template_id" /></label>
                  <label>Nombre del mapeo<input value={newMapName} onChange={(event) => setNewMapName(event.target.value)} placeholder="Beneficiarios entregados" /></label>
                  <label>Tabla/dataset destino<input value={newMapTargetTable} onChange={(event) => setNewMapTargetTable(event.target.value)} placeholder="beneficiarios" /></label>
                  <label>
                    Mapeo de campos (JSON: campo del formulario -&gt; columna destino)
                    <textarea rows={6} value={newMapFieldsJson} onChange={(event) => setNewMapFieldsJson(event.target.value)} />
                  </label>
                  <button className="primary" disabled={!newMapName.trim() || !newMapTargetTable.trim()} onClick={() => void submitNewMap()}>Crear mapeo</button>
                </div>
                <div className="ds-map-list">
                  <h2>Mapeos existentes</h2>
                  {maps.length ? maps.map((map) => (
                    <article className="ds-map-card" key={map.id}>
                      <strong>{map.name}</strong>
                      <span>Tabla destino: {map.target_table}</span>
                      <small>Plantilla: {map.template_id ?? 'sin vincular'} · Estado: {map.status}</small>
                      <code>{map.fields_json}</code>
                    </article>
                  )) : <p>Esta fuente aun no tiene mapeos.</p>}
                </div>
              </>
            )}
          </section>
        ) : null}

        {tab === 'jobs' ? (
          <section className="ds-jobs">
            {!selectedSource ? <p>Selecciona una fuente primero en la pestaña "Fuentes".</p> : (
              <div className="audit-table-wrap">
                <table className="audit-table">
                  <thead>
                    <tr>
                      <th>Estado</th>
                      <th>Modo</th>
                      <th>Registro</th>
                      <th>Mapeo</th>
                      <th>Resultado</th>
                    </tr>
                  </thead>
                  <tbody>
                    {jobs.map((job) => (
                      <tr key={job.id}>
                        <td><span className={`wa-status ${job.status === 'sent' ? 'sent' : job.status === 'failed' ? 'failed' : 'skipped'}`}>{jobStatusLabel(job.status)}</span></td>
                        <td>{job.mode}</td>
                        <td>{job.reference_record_id ?? '—'}</td>
                        <td>{job.map_id ?? '—'}</td>
                        <td>{job.last_result ? <code>{job.last_result.length > 140 ? `${job.last_result.slice(0, 140)}…` : job.last_result}</code> : '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {!jobs.length ? <p>Esta fuente aun no tiene envios registrados.</p> : null}
              </div>
            )}
          </section>
        ) : null}
      </main>
    </AppShell>
  );
}
