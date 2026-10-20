import { useEffect, useState } from 'react';

import { AppShell } from '../../components/AppShell';
import { useI18n } from '../../i18n';
import { PROJECT_KEY } from '../auth/session';
import {
  createMirrorPlan,
  createMirrorTarget,
  fetchBIConnectionInfo,
  fetchMirrorPlans,
  fetchMirrorRuns,
  fetchMirrorTargets,
  runMirrorPlan,
  testMirrorConnection,
} from './mirrorApi';
import type { BIConnectionInfo, MirrorPlan, MirrorRun, MirrorTarget } from './mirrorApi';
import { createScheduledTask, fetchScheduledTasks } from './schedulerApi';
import { DbImportPanel } from './DbImportPanel';
import type { MirrorRunSummary } from './mirrorApi';
import type { ScheduledTask } from './schedulerApi';

const ENGINE_LABELS: Record<string, string> = { postgres: 'PostgreSQL', mysql: 'MySQL', mssql: 'SQL Server', sqlite: 'SQLite' };
const MODE_KEYS: Record<string, string> = { full_mirror: 'admin.mirror.modeFull', insert_only: 'admin.mirror.modeInsert', incremental: 'admin.mirror.modeIncremental' };
const DEFAULT_PORTS: Record<string, number> = { postgres: 5432, mysql: 3306, mssql: 1433 };

export function MirrorApp() {
  const { t } = useI18n();
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';

  const [targets, setTargets] = useState<MirrorTarget[]>([]);
  const [selectedTarget, setSelectedTarget] = useState<MirrorTarget | null>(null);
  const [plans, setPlans] = useState<MirrorPlan[]>([]);
  const [runs, setRuns] = useState<MirrorRun[]>([]);
  const [selectedPlan, setSelectedPlan] = useState<MirrorPlan | null>(null);
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);

  // New target form
  const [showNewTarget, setShowNewTarget] = useState(false);
  const [tName, setTName] = useState('');
  const [tEngine, setTEngine] = useState<'postgres' | 'mysql' | 'mssql' | 'sqlite'>('postgres');
  const [tHost, setTHost] = useState('');
  const [tPort, setTPort] = useState(5432);
  const [tDatabase, setTDatabase] = useState('');
  const [tUsername, setTUsername] = useState('');
  const [tPassword, setTPassword] = useState('');
  const [tFilePath, setTFilePath] = useState('');

  // New plan form
  const [showNewPlan, setShowNewPlan] = useState(false);
  const [pName, setPName] = useState('');
  const [pMode, setPMode] = useState<'full_mirror' | 'insert_only' | 'incremental'>('incremental');
  // docs/146: «Proyecto completo» copia todo con una sola conexión, sin configurar formulario por formulario.
  const [pScope, setPScope] = useState<'project' | 'records'>('project');
  const [schedTime, setSchedTime] = useState('02:00');
  const [schedTz, setSchedTz] = useState('America/Bogota');

  // BI connection
  const [biInfo, setBiInfo] = useState<BIConnectionInfo | null>(null);
  const [biTargetId, setBiTargetId] = useState<string | null>(null);

  // Schedule
  const [scheduledTask, setScheduledTask] = useState<ScheduledTask | null>(null);
  const [schedFreq, setSchedFreq] = useState('daily');
  const [scheduling, setScheduling] = useState(false);

  async function loadTargets() {
    try { setTargets(await fetchMirrorTargets(projectId)); } catch (e) { setMessage(e instanceof Error ? e.message : 'Error'); }
  }
  async function loadPlans(targetId: string) {
    try { setPlans(await fetchMirrorPlans(targetId)); } catch (e) { setMessage(e instanceof Error ? e.message : 'Error'); }
  }
  async function loadRuns(planId: string) {
    try { setRuns(await fetchMirrorRuns(planId)); } catch (e) { setMessage(e instanceof Error ? e.message : 'Error'); }
  }
  async function loadSchedule() {
    try {
      const tasks = await fetchScheduledTasks(projectId);
      setScheduledTask(tasks.find((t) => t.task_type === 'mirror') ?? null);
    } catch { /* ignore */ }
  }

  useEffect(() => { if (projectId) { loadTargets(); loadSchedule(); } }, [projectId]);

  async function handleCreateTarget() {
    setLoading(true);
    try {
      const payload: any = { project_id: projectId, name: tName, engine: tEngine };
      if (tEngine === 'sqlite') { payload.file_path = tFilePath; }
      else { payload.host = tHost; payload.port = tPort; payload.database = tDatabase; payload.username = tUsername; payload.password = tPassword; }
      await createMirrorTarget(payload);
      setShowNewTarget(false);
      setTName(''); setTHost(''); setTDatabase(''); setTUsername(''); setTPassword(''); setTFilePath('');
      await loadTargets();
      setMessage(t('admin.mirror.targetCreated'));
    } catch (e) { setMessage(e instanceof Error ? e.message : 'Error'); }
    setLoading(false);
  }

  async function handleTestConnection(targetId: string) {
    setLoading(true);
    try {
      const result = await testMirrorConnection(targetId);
      setMessage(result.message);
      await loadTargets();
    } catch (e) { setMessage(e instanceof Error ? e.message : 'Error'); }
    setLoading(false);
  }

  async function handleShowBI(targetId: string) {
    if (biTargetId === targetId) { setBiInfo(null); setBiTargetId(null); return; }
    setLoading(true);
    try {
      const info = await fetchBIConnectionInfo(targetId);
      setBiInfo(info);
      setBiTargetId(targetId);
    } catch (e) { setMessage(e instanceof Error ? e.message : 'Error'); }
    setLoading(false);
  }

  async function handleSelectTarget(target: MirrorTarget) {
    setSelectedTarget(target);
    setSelectedPlan(null);
    setRuns([]);
    await loadPlans(target.id);
  }

  async function handleCreatePlan() {
    if (!selectedTarget) return;
    setLoading(true);
    try {
      await createMirrorPlan({ target_id: selectedTarget.id, name: pName, schedule_mode: pMode, scope: pScope });
      setShowNewPlan(false);
      setPName('');
      await loadPlans(selectedTarget.id);
      setMessage(t('admin.mirror.planCreated'));
    } catch (e) { setMessage(e instanceof Error ? e.message : 'Error'); }
    setLoading(false);
  }

  async function handleRunPlan(planId: string) {
    setLoading(true);
    try {
      const run = await runMirrorPlan(planId);
      setMessage(run.status === 'completed' || run.status === 'completed_with_differences'
        ? `${t('admin.mirror.runSuccess')}: ${run.records_synced} ${t('admin.mirror.records')}, ${run.values_synced} ${t('admin.mirror.values')}${run.summary ? (run.summary.reconciled ? ' · origen y destino cuadran' : ' · hay diferencias entre origen y destino, revisa la conciliación') : ''}`
        : `${t('admin.mirror.runFailed')}: ${run.error ?? ''}`);
      if (selectedTarget) await loadPlans(selectedTarget.id);
      if (selectedPlan?.id === planId) await loadRuns(planId);
    } catch (e) { setMessage(e instanceof Error ? e.message : 'Error'); }
    setLoading(false);
  }

  async function handleSelectPlan(plan: MirrorPlan) {
    setSelectedPlan(plan);
    await loadRuns(plan.id);
  }

  async function handleSchedule() {
    if (!selectedPlan) return;
    setScheduling(true);
    try {
      const config = schedFreq === 'hourly' || !schedTime ? null : JSON.stringify({ run_time: schedTime, timezone: schedTz || 'America/Bogota' });
      await createScheduledTask({ project_id: projectId, name: `Espejo: ${selectedPlan.name}`, task_type: 'mirror', target_id: selectedPlan.id, frequency: schedFreq, config_json: config });
      await loadSchedule();
      setMessage(t('admin.mirror.scheduled'));
    } catch (e) { setMessage(e instanceof Error ? e.message : 'Error'); }
    setScheduling(false);
  }

  function statusBadge(status: string) {
    const cls = status === 'active' || status === 'completed' ? 'sent' : status === 'failed' || status === 'connection_error' ? 'failed' : 'skipped';
    return <span className={`approval-badge ${cls}`}>{status}</span>;
  }

  return (
    <AppShell title={t('admin.mirror.title')}>
      <h2>{t('admin.mirror.title')}</h2>
      {message && <p className="form-message" onClick={() => setMessage('')}>{message}</p>}

      {/* Targets Section */}
      <section style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <h3>{t('admin.mirror.targets')}</h3>
          <button className="btn btn-primary" onClick={() => setShowNewTarget(!showNewTarget)}>{showNewTarget ? t('common.cancel') : t('admin.mirror.newTarget')}</button>
        </div>

        {showNewTarget && (
          <div className="card" style={{ padding: 16, marginBottom: 16 }}>
            <div style={{ display: 'grid', gap: 12 }}>
              <input placeholder={t('admin.mirror.targetName')} value={tName} onChange={(e) => setTName(e.target.value)} />
              <select value={tEngine} onChange={(e) => { const eng = e.target.value as any; setTEngine(eng); setTPort(DEFAULT_PORTS[eng] ?? 5432); }}>
                {Object.entries(ENGINE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
              {tEngine !== 'sqlite' ? (
                <>
                  <input placeholder={t('admin.mirror.host')} value={tHost} onChange={(e) => setTHost(e.target.value)} />
                  <input type="number" placeholder={t('admin.mirror.port')} value={tPort} onChange={(e) => setTPort(Number(e.target.value))} />
                  <input placeholder={t('admin.mirror.database')} value={tDatabase} onChange={(e) => setTDatabase(e.target.value)} />
                  <input placeholder={t('admin.mirror.username')} value={tUsername} onChange={(e) => setTUsername(e.target.value)} />
                  <input type="password" placeholder={t('admin.mirror.password')} value={tPassword} onChange={(e) => setTPassword(e.target.value)} />
                </>
              ) : (
                <input placeholder={t('admin.mirror.filePath')} value={tFilePath} onChange={(e) => setTFilePath(e.target.value)} />
              )}
              <button className="btn btn-primary" disabled={loading || !tName} onClick={handleCreateTarget}>{t('admin.mirror.createTarget')}</button>
            </div>
          </div>
        )}

        {targets.length === 0 ? <p style={{ color: 'var(--text-muted)' }}>{t('admin.mirror.noTargets')}</p> : (
          <table className="data-table">
            <thead><tr><th>{t('common.name')}</th><th>{t('admin.mirror.engine')}</th><th>{t('common.status')}</th><th>{t('common.actions')}</th></tr></thead>
            <tbody>
              {targets.map((target) => (
                <tr key={target.id} className={selectedTarget?.id === target.id ? 'selected-row' : ''}>
                  <td><button className="btn-link" onClick={() => handleSelectTarget(target)}>{target.name}</button></td>
                  <td>{ENGINE_LABELS[target.engine] ?? target.engine}</td>
                  <td>{statusBadge(target.status)}</td>
                  <td style={{ display: 'flex', gap: 4 }}>
                    <button className="btn btn-sm" onClick={() => handleTestConnection(target.id)} disabled={loading}>{t('admin.mirror.testConnection')}</button>
                    {target.engine !== 'sqlite' && <button className="btn btn-sm" onClick={() => handleShowBI(target.id)} disabled={loading}>{t('admin.mirror.biConnect')}</button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {/* BI Connection Info Panel */}
      {biInfo && biTargetId && (
        <section style={{ marginBottom: 24 }}>
          <div className="card" style={{ padding: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <h3 style={{ margin: 0 }}>{t('admin.mirror.biConnectionTitle')}</h3>
              <button className="btn btn-sm" onClick={() => { setBiInfo(null); setBiTargetId(null); }}>✕</button>
            </div>
            <div style={{ display: 'grid', gap: 8, fontSize: '0.9em' }}>
              <div><strong>{t('admin.mirror.engine')}:</strong> {ENGINE_LABELS[biInfo.engine] ?? biInfo.engine}</div>
              <div><strong>{t('admin.mirror.host')}:</strong> {biInfo.host}:{biInfo.port}</div>
              <div><strong>{t('admin.mirror.database')}:</strong> {biInfo.database}</div>
              <div><strong>{t('admin.mirror.username')}:</strong> {biInfo.username}</div>
              <div><strong>JDBC:</strong> <code style={{ wordBreak: 'break-all' }}>{biInfo.jdbc_url}</code></div>
              <div><strong>{t('admin.mirror.biTables')}:</strong> {biInfo.tables.length > 0 ? biInfo.tables.join(', ') : '—'}</div>
              <hr style={{ margin: '8px 0' }} />
              <h4 style={{ margin: 0 }}>{t('admin.mirror.biToolSetup')}</h4>
              {Object.entries(biInfo.tools).map(([tool, params]) => (
                <details key={tool} style={{ marginBottom: 4 }}>
                  <summary style={{ cursor: 'pointer', fontWeight: 600 }}>{tool}</summary>
                  <div style={{ paddingLeft: 16, paddingTop: 4 }}>
                    {Object.entries(params).map(([k, v]) => (
                      <div key={k}><strong>{k}:</strong> <code style={{ wordBreak: 'break-all' }}>{v}</code></div>
                    ))}
                  </div>
                </details>
              ))}
              <p style={{ color: 'var(--text-muted)', fontSize: '0.85em', margin: '8px 0 0' }}>{t('admin.mirror.biPasswordNote')}</p>
            </div>
          </div>
        </section>
      )}

      {/* Plans Section */}
      {selectedTarget && (
        <section style={{ marginBottom: 24 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <h3>{t('admin.mirror.plans')} — {selectedTarget.name}</h3>
            <button className="btn btn-primary" onClick={() => setShowNewPlan(!showNewPlan)}>{showNewPlan ? t('common.cancel') : t('admin.mirror.newPlan')}</button>
          </div>

          {showNewPlan && (
            <div className="card" style={{ padding: 16, marginBottom: 16 }}>
              <div style={{ display: 'grid', gap: 12 }}>
                <input placeholder={t('admin.mirror.planName')} value={pName} onChange={(e) => setPName(e.target.value)} />
                <label>Qué copiar<select value={pScope} onChange={(e) => setPScope(e.target.value as 'project' | 'records')}>
                  <option value="project">Proyecto completo: participantes, asignaciones, respuestas y una tabla por formulario (recomendado)</option>
                  <option value="records">Solo registros en formato clave-valor (modo anterior)</option>
                </select></label>
                <select value={pMode} onChange={(e) => setPMode(e.target.value as any)}>
                  {Object.entries(MODE_KEYS).map(([k, tk]) => <option key={k} value={k}>{t(tk)}</option>)}
                </select>
                <button className="btn btn-primary" disabled={loading || !pName} onClick={handleCreatePlan}>{t('admin.mirror.createPlan')}</button>
              </div>
            </div>
          )}

          {plans.length === 0 ? <p style={{ color: 'var(--text-muted)' }}>{t('admin.mirror.noPlans')}</p> : (
            <table className="data-table">
              <thead><tr><th>{t('common.name')}</th><th>Qué copia</th><th>{t('admin.mirror.mode')}</th><th>{t('admin.mirror.lastResult')}</th><th>{t('common.actions')}</th></tr></thead>
              <tbody>
                {plans.map((plan) => (
                  <tr key={plan.id} className={selectedPlan?.id === plan.id ? 'selected-row' : ''}>
                    <td><button className="btn-link" onClick={() => handleSelectPlan(plan)}>{plan.name}</button></td>
                    <td>{plan.scope === 'project' ? 'Proyecto completo' : 'Registros clave-valor'}</td>
                    <td>{t(MODE_KEYS[plan.schedule_mode] ?? 'admin.mirror.modeFull')}</td>
                    <td style={{ fontSize: '0.85em' }}>{plan.last_result ?? '—'}</td>
                    <td>
                      <button className="btn btn-sm" onClick={() => handleRunPlan(plan.id)} disabled={loading}>{t('admin.mirror.runNow')}</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      )}

      {/* Schedule Section */}
      {selectedPlan && (
        <section style={{ marginBottom: 24 }}>
          <h3>{t('admin.mirror.schedule')}</h3>
          {scheduledTask ? (
            <p>{t('admin.mirror.scheduledAs')}: <strong>{scheduledTask.name}</strong> ({scheduledTask.frequency}) — {scheduledTask.status}</p>
          ) : (
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <select value={schedFreq} onChange={(e) => setSchedFreq(e.target.value)}>
                <option value="hourly">{t('admin.backups.frequencyHourly')}</option>
                <option value="daily">{t('admin.backups.frequencyDaily')}</option>
                <option value="weekly">{t('admin.backups.frequencyWeekly')}</option>
              </select>
              {schedFreq !== 'hourly' ? <>
                <label>Hora<input type="time" value={schedTime} onChange={(e) => setSchedTime(e.target.value)} /></label>
                <label>Zona horaria<input value={schedTz} onChange={(e) => setSchedTz(e.target.value)} /></label>
              </> : null}
              <button className="btn btn-primary" onClick={handleSchedule} disabled={scheduling}>{t('admin.mirror.scheduleBtn')}</button>
            </div>
          )}
        </section>
      )}

      {selectedPlan && runs[0]?.summary ? <Reconciliation summary={runs[0].summary} /> : null}

      {selectedTarget && <DbImportPanel projectId={projectId} source={selectedTarget} />}

      {/* Runs Section */}
      {selectedPlan && runs.length > 0 && (
        <section>
          <h3>{t('admin.mirror.runs')}</h3>
          <table className="data-table">
            <thead><tr><th>{t('common.status')}</th><th>{t('admin.mirror.records')}</th><th>{t('admin.mirror.values')}</th><th>{t('admin.mirror.startedAt')}</th><th>{t('admin.mirror.finishedAt')}</th></tr></thead>
            <tbody>
              {runs.map((run) => (
                <tr key={run.id}>
                  <td>{statusBadge(run.status)}</td>
                  <td>{run.records_synced}</td>
                  <td>{run.values_synced}</td>
                  <td style={{ fontSize: '0.85em' }}>{new Date(run.started_at).toLocaleString()}</td>
                  <td style={{ fontSize: '0.85em' }}>{run.finished_at ? new Date(run.finished_at).toLocaleString() : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </AppShell>
  );
}

/** Conciliación de la última corrida: filas de origen frente a destino por tabla (docs/146). */
function Reconciliation({ summary }: { summary: MirrorRunSummary }) {
  const rows = [...Object.entries(summary.tables).map(([name, item]) => ({ name, label: name, ...item })),
    ...Object.entries(summary.form_tables).map(([name, item]) => ({ name, label: `${item.form ?? name} (${name}, ${item.columns ?? 0} preguntas)`, ...item }))];
  return <section style={{ marginBottom: 24 }}>
    <h3>Conciliación de la última corrida {summary.reconciled ? '— origen y destino cuadran' : '— hay diferencias'}</h3>
    <table className="data-table"><thead><tr><th>Tabla en la base externa</th><th>Origen</th><th>Destino</th><th>Estado</th></tr></thead>
      <tbody>{rows.map((row) => <tr key={row.name}><td>{row.label}</td><td>{row.source}</td><td>{row.destination}</td><td>{row.ok ? 'Cuadra' : 'Diferencia'}</td></tr>)}</tbody></table>
  </section>;
}
