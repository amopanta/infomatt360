import { Fragment, useEffect, useState } from 'react';

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
const STATUS_LABELS: Record<string, string> = { active: 'Conectada', inactive: 'Inactiva', completed: 'Completada', running: 'En curso', failed: 'Falló', connection_error: 'Sin conexión', pending: 'Pendiente' };

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
  // Con una sola base conectada se abre directamente: antes habia que descubrir
  // que el nombre era un boton para ver la copia y la importacion (docs/150).
  useEffect(() => { if (!selectedTarget && targets.length === 1) void handleSelectTarget(targets[0]); }, [targets]);
  useEffect(() => { if (selectedTarget && !selectedPlan && plans.length === 1) void handleSelectPlan(plans[0]); }, [plans]);

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
    return <span className={`approval-badge ${cls}`}>{STATUS_LABELS[status] ?? status}</span>;
  }

  return (
    <AppShell title={t('admin.mirror.title')}>
      <main className="module-page">
        <header className="module-intro">
          <h2>{t('admin.mirror.title')}</h2>
          <p>{t('admin.mirror.intro')}</p>
          <ol className="module-steps">
            <li className={targets.length ? 'done' : 'current'}><strong>{t('admin.mirror.step1')}</strong><span>{t('admin.mirror.step1Text')}</span></li>
            <li className={plans.length ? 'done' : targets.length ? 'current' : ''}><strong>{t('admin.mirror.step2')}</strong><span>{t('admin.mirror.step2Text')}</span></li>
            <li className={targets.length ? 'current' : ''}><strong>{t('admin.mirror.step3')}</strong><span>{t('admin.mirror.step3Text')}</span></li>
          </ol>
        </header>
        {message && <p className="form-message" role="status" onClick={() => setMessage('')}>{message}</p>}

        <section className="panel">
          <header className="panel-head">
            <div><h3>{t('admin.mirror.targets')}</h3><p>{t('admin.mirror.targetsHelp')}</p></div>
            <button className={showNewTarget ? 'btn' : 'btn btn-primary'} onClick={() => setShowNewTarget(!showNewTarget)}>{showNewTarget ? t('common.cancel') : t('admin.mirror.newTarget')}</button>
          </header>

          {showNewTarget && (
            <div className="form-grid module-form">
              <label>{t('admin.mirror.targetName')}<input value={tName} onChange={(e) => setTName(e.target.value)} placeholder={t('admin.mirror.targetNameExample')} /></label>
              <label>{t('admin.mirror.engine')}<select value={tEngine} onChange={(e) => { const eng = e.target.value as typeof tEngine; setTEngine(eng); setTPort(DEFAULT_PORTS[eng] ?? 5432); }}>
                {Object.entries(ENGINE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select></label>
              {tEngine !== 'sqlite' ? (
                <>
                  <label>{t('admin.mirror.host')}<input value={tHost} onChange={(e) => setTHost(e.target.value)} /></label>
                  <label>{t('admin.mirror.port')}<input type="number" value={tPort} onChange={(e) => setTPort(Number(e.target.value))} /></label>
                  <label>{t('admin.mirror.database')}<input value={tDatabase} onChange={(e) => setTDatabase(e.target.value)} /></label>
                  <label>{t('admin.mirror.username')}<input value={tUsername} onChange={(e) => setTUsername(e.target.value)} autoComplete="off" /></label>
                  <label>{t('admin.mirror.password')}<input type="password" value={tPassword} onChange={(e) => setTPassword(e.target.value)} autoComplete="new-password" /></label>
                </>
              ) : (
                <label className="form-wide">{t('admin.mirror.filePath')}<input value={tFilePath} onChange={(e) => setTFilePath(e.target.value)} /></label>
              )}
              <div className="form-wide"><button className="btn btn-primary" disabled={loading || !tName} onClick={handleCreateTarget}>{t('admin.mirror.createTarget')}</button></div>
            </div>
          )}

          {targets.length === 0 ? <p className="empty-note">{t('admin.mirror.noTargets')}</p> : (
            <table className="data-table">
              <thead><tr><th>{t('common.name')}</th><th>{t('admin.mirror.engine')}</th><th>{t('common.status')}</th><th>{t('common.actions')}</th></tr></thead>
              <tbody>
                {targets.map((target) => (
                  <tr key={target.id} className={selectedTarget?.id === target.id ? 'selected-row' : ''}>
                    <td><button className="btn-link" onClick={() => handleSelectTarget(target)}>{target.name}</button>{selectedTarget?.id === target.id ? <small className="row-note">{t('admin.mirror.selected')}</small> : null}</td>
                    <td>{ENGINE_LABELS[target.engine] ?? target.engine}</td>
                    <td>{statusBadge(target.status)}</td>
                    <td className="row-actions">
                      <button className="btn btn-sm" onClick={() => handleTestConnection(target.id)} disabled={loading}>{t('admin.mirror.testConnection')}</button>
                      {target.engine !== 'sqlite' && <button className="btn btn-sm" onClick={() => handleShowBI(target.id)} disabled={loading}>{t('admin.mirror.biConnect')}</button>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        {biInfo && biTargetId && (
          <section className="panel">
            <header className="panel-head">
              <h3>{t('admin.mirror.biConnectionTitle')}</h3>
              <button className="btn btn-sm" aria-label={t('common.close')} onClick={() => { setBiInfo(null); setBiTargetId(null); }}>✕</button>
            </header>
            <dl className="detail-list">
              <dt>{t('admin.mirror.engine')}</dt><dd>{ENGINE_LABELS[biInfo.engine] ?? biInfo.engine}</dd>
              <dt>{t('admin.mirror.host')}</dt><dd>{biInfo.host}:{biInfo.port}</dd>
              <dt>{t('admin.mirror.database')}</dt><dd>{biInfo.database}</dd>
              <dt>{t('admin.mirror.username')}</dt><dd>{biInfo.username}</dd>
              <dt>JDBC</dt><dd><code>{biInfo.jdbc_url}</code></dd>
              <dt>{t('admin.mirror.biTables')}</dt><dd>{biInfo.tables.length > 0 ? biInfo.tables.join(', ') : '—'}</dd>
            </dl>
            <h4>{t('admin.mirror.biToolSetup')}</h4>
            {Object.entries(biInfo.tools).map(([tool, params]) => (
              <details key={tool} className="detail-toggle">
                <summary>{tool}</summary>
                <dl className="detail-list">{Object.entries(params).map(([k, v]) => <Fragment key={k}><dt>{k}</dt><dd><code>{v}</code></dd></Fragment>)}</dl>
              </details>
            ))}
            <p className="empty-note">{t('admin.mirror.biPasswordNote')}</p>
          </section>
        )}

        {selectedTarget && (
          <section className="panel">
            <header className="panel-head">
              <div><h3>{t('admin.mirror.plansFor', { name: selectedTarget.name })}</h3><p>{t('admin.mirror.plansHelp')}</p></div>
              <button className={showNewPlan ? 'btn' : 'btn btn-primary'} onClick={() => setShowNewPlan(!showNewPlan)}>{showNewPlan ? t('common.cancel') : t('admin.mirror.newPlan')}</button>
            </header>

            {showNewPlan && (
              <div className="form-grid module-form">
                <label>{t('admin.mirror.planName')}<input value={pName} onChange={(e) => setPName(e.target.value)} /></label>
                <label>{t('admin.mirror.mode')}<select value={pMode} onChange={(e) => setPMode(e.target.value as typeof pMode)}>
                  {Object.entries(MODE_KEYS).map(([k, tk]) => <option key={k} value={k}>{t(tk)}</option>)}
                </select></label>
                <label className="form-wide">{t('admin.mirror.scope')}<select value={pScope} onChange={(e) => setPScope(e.target.value as 'project' | 'records')}>
                  <option value="project">{t('admin.mirror.scopeProject')}</option>
                  <option value="records">{t('admin.mirror.scopeRecords')}</option>
                </select></label>
                <div className="form-wide"><button className="btn btn-primary" disabled={loading || !pName} onClick={handleCreatePlan}>{t('admin.mirror.createPlan')}</button></div>
              </div>
            )}

            {plans.length === 0 ? <p className="empty-note">{t('admin.mirror.noPlans')}</p> : (
              <table className="data-table">
                <thead><tr><th>{t('common.name')}</th><th>{t('admin.mirror.scope')}</th><th>{t('admin.mirror.mode')}</th><th>{t('admin.mirror.lastResult')}</th><th>{t('common.actions')}</th></tr></thead>
                <tbody>
                  {plans.map((plan) => (
                    <tr key={plan.id} className={selectedPlan?.id === plan.id ? 'selected-row' : ''}>
                      <td><button className="btn-link" onClick={() => handleSelectPlan(plan)}>{plan.name}</button></td>
                      <td>{plan.scope === 'project' ? t('admin.mirror.scopeProjectShort') : t('admin.mirror.scopeRecordsShort')}</td>
                      <td>{t(MODE_KEYS[plan.schedule_mode] ?? 'admin.mirror.modeFull')}</td>
                      <td className="cell-muted">{plan.last_result ?? '—'}</td>
                      <td className="row-actions"><button className="btn btn-sm btn-primary" onClick={() => handleRunPlan(plan.id)} disabled={loading}>{t('admin.mirror.runNow')}</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}

            {selectedPlan && (
              <div className="schedule-row">
                <h4>{t('admin.mirror.schedule')}</h4>
                {scheduledTask ? (
                  <p>{t('admin.mirror.scheduledAs')}: <strong>{scheduledTask.name}</strong> ({scheduledTask.frequency}) · {scheduledTask.status}</p>
                ) : (
                  <div className="form-inline">
                    <label>{t('admin.mirror.frequency')}<select value={schedFreq} onChange={(e) => setSchedFreq(e.target.value)}>
                      <option value="hourly">{t('admin.backups.frequencyHourly')}</option>
                      <option value="daily">{t('admin.backups.frequencyDaily')}</option>
                      <option value="weekly">{t('admin.backups.frequencyWeekly')}</option>
                    </select></label>
                    {schedFreq !== 'hourly' ? <>
                      <label>{t('admin.mirror.time')}<input type="time" value={schedTime} onChange={(e) => setSchedTime(e.target.value)} /></label>
                      <label>{t('admin.mirror.timezone')}<input value={schedTz} onChange={(e) => setSchedTz(e.target.value)} /></label>
                    </> : null}
                    <button className="btn btn-primary" onClick={handleSchedule} disabled={scheduling}>{t('admin.mirror.scheduleBtn')}</button>
                  </div>
                )}
              </div>
            )}
          </section>
        )}

        {selectedPlan && runs[0]?.summary ? <Reconciliation summary={runs[0].summary} /> : null}

        {selectedPlan && runs.length > 0 && (
          <section className="panel">
            <header className="panel-head"><h3>{t('admin.mirror.runs')}</h3></header>
            <table className="data-table">
              <thead><tr><th>{t('common.status')}</th><th>{t('admin.mirror.records')}</th><th>{t('admin.mirror.values')}</th><th>{t('admin.mirror.startedAt')}</th><th>{t('admin.mirror.finishedAt')}</th></tr></thead>
              <tbody>
                {runs.map((run) => (
                  <tr key={run.id}>
                    <td>{statusBadge(run.status)}</td>
                    <td>{run.records_synced}</td>
                    <td>{run.values_synced}</td>
                    <td className="cell-muted">{new Date(run.started_at).toLocaleString()}</td>
                    <td className="cell-muted">{run.finished_at ? new Date(run.finished_at).toLocaleString() : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        )}

        {selectedTarget && <DbImportPanel projectId={projectId} source={selectedTarget} />}
      </main>
    </AppShell>
  );
}

/** Conciliación de la última corrida: filas de origen frente a destino por tabla (docs/146). */
function Reconciliation({ summary }: { summary: MirrorRunSummary }) {
  const rows = [...Object.entries(summary.tables).map(([name, item]) => ({ name, label: name, ...item })),
    ...Object.entries(summary.form_tables).map(([name, item]) => ({ name, label: `${item.form ?? name} (${name}, ${item.columns ?? 0} preguntas)`, ...item }))];
  return <section className="panel">
    <header className="panel-head"><div><h3>Conciliación de la última copia</h3><p>{summary.reconciled ? 'Origen y destino cuadran en todas las tablas.' : 'Hay tablas con diferencias entre origen y destino.'}</p></div></header>
    <table className="data-table"><thead><tr><th>Tabla en la base externa</th><th>Origen</th><th>Destino</th><th>Estado</th></tr></thead>
      <tbody>{rows.map((row) => <tr key={row.name}><td>{row.label}</td><td>{row.source}</td><td>{row.destination}</td><td><span className={`approval-badge ${row.ok ? 'sent' : 'failed'}`}>{row.ok ? 'Cuadra' : 'Diferencia'}</span></td></tr>)}</tbody></table>
  </section>;
}
