import { useEffect, useState } from 'react';

import { AppShell } from '../../components/AppShell';
import { useI18n } from '../../i18n';
import { PROJECT_KEY } from '../auth/session';
import { createMap, createSource, fetchJobs, fetchMaps, fetchSources } from './donorSyncApi';
import type { IntegrationJob, IntegrationMap, IntegrationSource } from './donorSyncApi';

type Tab = 'sources' | 'maps' | 'jobs';

export function DonorSyncApp() {
  const { t } = useI18n();
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

  function jobStatusLabel(status: string) {
    const labels: Record<string, string> = {
      sent: t('admin.donorSync.statusSent'),
      failed: t('admin.donorSync.statusFailed'),
      pending: t('admin.donorSync.statusPending'),
    };
    return labels[status] ?? status;
  }

  async function loadSources() {
    try {
      const rows = await fetchSources(projectId);
      setSources(rows);
      if (!selectedSourceId && rows[0]) setSelectedSourceId(rows[0].id);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('admin.donorSync.errorLoadSources'));
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
      setMessage(t('admin.donorSync.sourceCreated'));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('admin.donorSync.errorCreateSource'));
    }
  }

  async function loadMaps() {
    if (!selectedSourceId) return;
    try {
      setMaps(await fetchMaps(selectedSourceId));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('admin.donorSync.errorLoadMaps'));
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
      setMessage(t('admin.donorSync.mapCreated'));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('admin.donorSync.errorCreateMap'));
    }
  }

  async function loadJobs() {
    if (!selectedSourceId) return;
    try {
      setJobs(await fetchJobs(selectedSourceId));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('admin.donorSync.errorLoadJobs'));
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
    <AppShell title={t('admin.donorSync.title')}>
      <main className="ds-shell">
        <nav className="erp-tabs">
          <button className={tab === 'sources' ? 'active' : undefined} onClick={() => setTab('sources')}>{t('admin.donorSync.tabSources')}</button>
          <button className={tab === 'maps' ? 'active' : undefined} onClick={() => setTab('maps')}>{t('admin.donorSync.tabMaps')}</button>
          <button className={tab === 'jobs' ? 'active' : undefined} onClick={() => setTab('jobs')}>{t('admin.donorSync.tabJobs')}</button>
        </nav>
        {message ? <p role="status" className="erp-message">{message}</p> : null}

        {tab === 'sources' ? (
          <section className="ds-sources">
            <div className="ds-source-create">
              <h2>{t('admin.donorSync.newSourceTitle')}</h2>
              <p>{t('admin.donorSync.newSourceDescription')}</p>
              <label>{t('admin.donorSync.nameLabel')}<input value={newSourceName} onChange={(event) => setNewSourceName(event.target.value)} placeholder={t('admin.donorSync.namePlaceholder')} /></label>
              <label>
                {t('admin.donorSync.typeLabel')}
                <select value={newSourceType} onChange={(event) => setNewSourceType(event.target.value)}>
                  <option value="activityinfo">{t('admin.donorSync.typeActivityInfo')}</option>
                  <option value="toladata">{t('admin.donorSync.typeTolaData')}</option>
                  <option value="other">{t('admin.donorSync.typeOther')}</option>
                </select>
              </label>
              <label>{t('admin.donorSync.urlLabel')}<input value={newSourceUrl} onChange={(event) => setNewSourceUrl(event.target.value)} placeholder={t('admin.donorSync.urlPlaceholder')} /></label>
              <label>{t('admin.donorSync.credentialsLabel')}<input value={newSourceCredentials} onChange={(event) => setNewSourceCredentials(event.target.value)} type="password" placeholder={t('admin.donorSync.optionalPlaceholder')} /></label>
              <button className="primary" disabled={!newSourceName.trim() || !newSourceUrl.trim()} onClick={() => void submitNewSource()}>{t('admin.donorSync.createSource')}</button>
            </div>
            <div className="ds-source-list">
              <h2>{t('admin.donorSync.projectSources')}</h2>
              {sources.length ? sources.map((source) => (
                <article className={selectedSourceId === source.id ? 'ds-source-card active' : 'ds-source-card'} key={source.id}>
                  <button onClick={() => setSelectedSourceId(source.id)}>
                    <strong>{source.name}</strong>
                    <span>{source.source_type} · {source.status}</span>
                    <small>{source.base_url ?? t('admin.donorSync.noUrlConfigured')}</small>
                    <small>{source.has_credentials ? t('admin.donorSync.withCredentials') : t('admin.donorSync.withoutCredentials')}</small>
                  </button>
                </article>
              )) : <p>{t('admin.donorSync.noSourcesYet')}</p>}
            </div>
          </section>
        ) : null}

        {tab === 'maps' ? (
          <section className="ds-maps">
            {!selectedSource ? <p>{t('admin.donorSync.selectSourceFirst')}</p> : (
              <>
                <div className="ds-map-create">
                  <h2>{t('admin.donorSync.newMapFor', { name: selectedSource.name })}</h2>
                  <p>{t('admin.donorSync.mapDescription')}</p>
                  <label>{t('admin.donorSync.templateIdLabel')}<input value={newMapTemplateId} onChange={(event) => setNewMapTemplateId(event.target.value)} placeholder={t('admin.donorSync.templateIdPlaceholder')} /></label>
                  <label>{t('admin.donorSync.mapNameLabel')}<input value={newMapName} onChange={(event) => setNewMapName(event.target.value)} placeholder={t('admin.donorSync.mapNamePlaceholder')} /></label>
                  <label>{t('admin.donorSync.targetTableLabel')}<input value={newMapTargetTable} onChange={(event) => setNewMapTargetTable(event.target.value)} placeholder={t('admin.donorSync.targetTablePlaceholder')} /></label>
                  <label>
                    {t('admin.donorSync.fieldsJsonLabel')}
                    <textarea rows={6} value={newMapFieldsJson} onChange={(event) => setNewMapFieldsJson(event.target.value)} />
                  </label>
                  <button className="primary" disabled={!newMapName.trim() || !newMapTargetTable.trim()} onClick={() => void submitNewMap()}>{t('admin.donorSync.createMap')}</button>
                </div>
                <div className="ds-map-list">
                  <h2>{t('admin.donorSync.existingMaps')}</h2>
                  {maps.length ? maps.map((map) => (
                    <article className="ds-map-card" key={map.id}>
                      <strong>{map.name}</strong>
                      <span>{t('admin.donorSync.targetTablePrefix', { table: map.target_table })}</span>
                      <small>{t('admin.donorSync.templateLabel', { template: map.template_id ?? t('admin.donorSync.notLinked') })} · {t('admin.donorSync.statusPrefix', { status: map.status })}</small>
                      <code>{map.fields_json}</code>
                    </article>
                  )) : <p>{t('admin.donorSync.noMapsYet')}</p>}
                </div>
              </>
            )}
          </section>
        ) : null}

        {tab === 'jobs' ? (
          <section className="ds-jobs">
            {!selectedSource ? <p>{t('admin.donorSync.selectSourceForJobs')}</p> : (
              <div className="audit-table-wrap">
                <table className="audit-table">
                  <thead>
                    <tr>
                      <th>{t('admin.donorSync.colStatus')}</th>
                      <th>{t('admin.donorSync.colMode')}</th>
                      <th>{t('admin.donorSync.colRecord')}</th>
                      <th>{t('admin.donorSync.colMap')}</th>
                      <th>{t('admin.donorSync.colResult')}</th>
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
                {!jobs.length ? <p>{t('admin.donorSync.noJobsYet')}</p> : null}
              </div>
            )}
          </section>
        ) : null}
      </main>
    </AppShell>
  );
}
