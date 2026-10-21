/** Planeador mensual (docs/144): tablero de cumplimiento, metas, programación, población y reglas. */
import { useEffect, useMemo, useState } from 'react';
import { AppShell } from '../../components/AppShell';
import { useI18n } from '../../i18n';
import { PROJECT_KEY } from '../auth/session';
import {
  cancelPlan, closeCut, createPlan, downloadExcel, downloadImportErrors, downloadTemplate, fetchCatalog, fetchDashboard, fetchPlans,
  fetchPopulation, fetchSettings, fetchTargets, formatCompliance, importTargets, reschedulePlan, savePopulation, saveSettings, saveTarget,
  type Filters, type ImportResult, type Metric, type PlannerCatalog, type PlannerPlan, type PlannerPopulation, type PlannerReport,
  type PlannerSettings, type PlannerTarget,
} from './api';

type Tab = 'dashboard' | 'targets' | 'plans' | 'population' | 'settings';
const MONTHS = ['', 'Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];

function Bar({ metric }: { metric: Metric }) {
  // La barra se limita al 100 % de ancho, el dato no.
  const width = metric.compliance === null ? 0 : Math.min(metric.compliance, 100);
  const level = metric.compliance === null ? 'none' : metric.compliance >= 100 ? 'ok' : metric.compliance >= 70 ? 'mid' : 'low';
  return <span className={`planner-bar planner-bar-${level}`} aria-hidden="true"><span style={{ width: `${width}%` }} /></span>;
}

export function PlannerApp() {
  const { t } = useI18n();
  const projectId = localStorage.getItem(PROJECT_KEY) || '';
  const now = new Date();
  const [tab, setTab] = useState<Tab>('dashboard');
  const [filters, setFilters] = useState<Filters>({ year: now.getFullYear(), month: now.getMonth() + 1 });
  const [catalog, setCatalog] = useState<PlannerCatalog | null>(null);
  const [report, setReport] = useState<PlannerReport | null>(null);
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const noGoal = t('planner.noGoal');
  const activityName = useMemo(() => new Map(catalog?.activities.map((a) => [a.id, a.name]) ?? []), [catalog]);
  const personName = useMemo(() => new Map(catalog?.people.map((p) => [p.id, p.full_name]) ?? []), [catalog]);

  async function refresh() {
    if (!projectId) return;
    setBusy(true);
    try { setReport(await fetchDashboard(projectId, filters)); setMessage(''); }
    catch (error) { setMessage(error instanceof Error ? error.message : String(error)); }
    finally { setBusy(false); }
  }

  useEffect(() => { if (projectId) void fetchCatalog(projectId).then(setCatalog).catch((error: Error) => setMessage(error.message)); }, [projectId]);
  useEffect(() => { void refresh(); }, [projectId, filters.year, filters.month, filters.municipality, filters.gestor_user_id, filters.template_id]);

  if (!projectId) return <AppShell title={t('planner.title')}><main className="planner-page"><p>{t('planner.selectProject')}</p></main></AppShell>;
  const manage = Boolean(catalog?.can_manage);
  const monthClosed = Boolean(filters.month && report?.closed_months.includes(Number(filters.month)));
  const tabs: Tab[] = manage ? ['dashboard', 'targets', 'plans', 'population', 'settings'] : ['dashboard', 'plans'];

  async function close() {
    if (!filters.month || !window.confirm(t('planner.closeConfirm', { month: MONTHS[Number(filters.month)], year: filters.year }))) return;
    try { await closeCut(projectId, filters.year, Number(filters.month)); setMessage(t('planner.closed')); await refresh(); }
    catch (error) { setMessage(error instanceof Error ? error.message : String(error)); }
  }

  return <AppShell title={t('planner.title')}><main className="planner-page">
    <header className="planner-head">
      <div><h1>{t('planner.title')}</h1><p>{t('planner.subtitle')}</p></div>
      <div className="planner-actions">
        <button type="button" onClick={() => void downloadExcel(projectId, filters).catch((error: Error) => setMessage(error.message))}>{t('planner.downloadExcel')}</button>
        {manage && filters.month && !monthClosed ? <button type="button" className="secondary" onClick={() => void close()}>{t('planner.closeCut')}</button> : null}
      </div>
    </header>
    <section className="planner-filters" aria-label={t('planner.filters')}>
      <label>{t('planner.year')}<input type="number" min={2000} max={2100} value={filters.year} onChange={(e) => setFilters({ ...filters, year: Number(e.target.value) || now.getFullYear() })} /></label>
      <label>{t('planner.month')}<select value={filters.month ?? ''} onChange={(e) => setFilters({ ...filters, month: e.target.value ? Number(e.target.value) : '' })}>
        <option value="">{t('planner.allYear')}</option>{MONTHS.slice(1).map((name, index) => <option key={name} value={index + 1}>{name}</option>)}</select></label>
      <label>{t('planner.municipality')}<input value={filters.municipality ?? ''} placeholder={t('planner.allAuthorized')} onChange={(e) => setFilters({ ...filters, municipality: e.target.value })} /></label>
      <label>{t('planner.activity')}<select value={filters.template_id ?? ''} onChange={(e) => setFilters({ ...filters, template_id: e.target.value })}>
        <option value="">{t('planner.all')}</option>{catalog?.activities.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}</select></label>
      {catalog?.supervise ? <label>{t('planner.gestor')}<select value={filters.gestor_user_id ?? ''} onChange={(e) => setFilters({ ...filters, gestor_user_id: e.target.value })}>
        <option value="">{t('planner.all')}</option>{catalog.people.map((p) => <option key={p.id} value={p.id}>{p.full_name}</option>)}</select></label> : null}
    </section>
    <nav className="my-forms-views" aria-label={t('planner.sections')}>
      {tabs.map((item) => <button key={item} type="button" aria-current={tab === item ? 'page' : undefined} onClick={() => setTab(item)}>{t(`planner.tab.${item}`)}</button>)}
    </nav>
    {message ? <p role="status" className="planner-message">{message}</p> : null}
    {monthClosed ? <p className="planner-closed">{t('planner.monthClosed')}</p> : null}
    {tab === 'dashboard' && <Dashboard report={report} busy={busy} noGoal={noGoal} />}
    {tab === 'targets' && catalog && <Targets projectId={projectId} year={filters.year} catalog={catalog} activityName={activityName} personName={personName} onChanged={refresh} closedMonths={report?.closed_months ?? []} />}
    {tab === 'plans' && catalog && <Plans projectId={projectId} year={filters.year} catalog={catalog} activityName={activityName} personName={personName} onChanged={refresh} />}
    {tab === 'population' && <Population projectId={projectId} year={filters.year} onChanged={refresh} />}
    {tab === 'settings' && <Settings projectId={projectId} onChanged={refresh} />}
  </main></AppShell>;
}

function Dashboard({ report, busy, noGoal }: { report: PlannerReport | null; busy: boolean; noGoal: string }) {
  const { t } = useI18n();
  if (!report) return <p>{busy ? t('planner.loading') : ''}</p>;
  const { activities, families } = report.totals;
  return <>
    <section className="devices-totals planner-totals" aria-label={t('planner.summary')}>
      <div><strong>{activities.target}</strong><span>{t('planner.goal')}</span></div>
      <div><strong>{activities.executed}</strong><span>{t('planner.executedValid')}</span></div>
      <div className={activities.pending ? 'is-warning' : ''}><strong>{activities.pending}</strong><span>{t('planner.pending')}</span></div>
      <div><strong>{formatCompliance(activities.compliance, noGoal)}</strong><span>{t('planner.compliance')}</span></div>
      {activities.unplanned ? <div className="is-warning"><strong>{activities.unplanned}</strong><span>{t('planner.unplanned')}</span></div> : null}
      <div><strong>{families.unique_all}</strong><span>{t('planner.uniqueFamilies')}</span></div>
      <div><strong>{families.coverage === null ? '—' : formatCompliance(families.coverage, noGoal)}</strong><span>{t('planner.coverage')}</span></div>
    </section>
    <section className="teams-card"><h2>{t('planner.municipalSummary')}</h2>
      <div className="records-table-wrap"><table className="records-table"><thead><tr>
        <th>{t('planner.month')}</th><th>{t('planner.municipality')}</th><th>{t('planner.activity')}</th><th>{t('planner.goal')}</th><th>{t('planner.executedValid')}</th>
        <th>{t('planner.pending')}</th><th>{t('planner.compliance')}</th><th>{t('planner.uniqueFamilies')}</th></tr></thead>
        <tbody>{report.municipal.map((row) => <tr key={`${row.month}-${row.municipality}-${row.template_id}`}>
          <td>{MONTHS[row.month]}{row.closed ? ' 🔒' : ''}</td><td>{row.municipality}</td><td>{row.activity}</td><td>{row.activities.target || '—'}</td>
          <td>{row.activities.executed}</td><td>{row.activities.pending}</td>
          <td><Bar metric={row.activities} /> {formatCompliance(row.activities.compliance, noGoal)}</td>
          <td>{row.families.executed}{row.families.target ? ` / ${row.families.target}` : ''}</td></tr>)}
          {!report.municipal.length && <tr><td colSpan={8}>{t('planner.empty')}</td></tr>}</tbody></table></div>
    </section>
    <section className="teams-card"><h2>{t('planner.gestorDetail')}</h2>
      <div className="records-table-wrap"><table className="records-table"><thead><tr>
        <th>{t('planner.month')}</th><th>{t('planner.coordinator')}</th><th>{t('planner.gestor')}</th><th>{t('planner.municipality')}</th><th>{t('planner.activity')}</th>
        <th>{t('planner.scheduled')}</th><th>{t('planner.goal')}</th><th>{t('planner.executedValid')}</th><th>{t('planner.compliance')}</th><th>{t('planner.state')}</th></tr></thead>
        <tbody>{report.gestor.map((row, index) => <tr key={index}>
          <td>{MONTHS[row.month]}</td><td>{row.coordinator || '—'}</td><td>{row.gestor}</td><td>{row.municipality}</td><td>{row.activity}</td>
          <td>{row.planned_quantity || '—'}{row.start_date ? ` (${row.start_date} → ${row.end_date})` : ''}</td><td>{row.activities.target || '—'}</td>
          <td>{row.activities.executed}</td><td>{formatCompliance(row.activities.compliance, noGoal)}</td><td>{row.state}</td></tr>)}
          {!report.gestor.length && <tr><td colSpan={10}>{t('planner.empty')}</td></tr>}</tbody></table></div>
    </section>
  </>;
}

function Targets({ projectId, year, catalog, activityName, personName, onChanged, closedMonths }: { projectId: string; year: number; catalog: PlannerCatalog; activityName: Map<string, string>; personName: Map<string, string>; onChanged: () => Promise<void>; closedMonths: number[] }) {
  const { t } = useI18n();
  const [rows, setRows] = useState<PlannerTarget[]>([]);
  const [form, setForm] = useState({ month: new Date().getMonth() + 1, municipality: '', template_id: '', gestor_user_id: '', unit: 'records' as 'records' | 'families', target: 0, reason: '' });
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [message, setMessage] = useState('');
  const load = () => fetchTargets(projectId, year).then(setRows).catch((error: Error) => setMessage(error.message));
  useEffect(() => { void load(); }, [projectId, year]);

  async function save() {
    try {
      const outcome = await saveTarget(projectId, { year, month: form.month, municipality: form.municipality, template_id: form.template_id, gestor_user_id: form.gestor_user_id || null, unit: form.unit, target: form.target, reason: form.reason });
      setMessage(t(`planner.outcome.${outcome.outcome}`));
      await load(); await onChanged();
    } catch (error) { setMessage(error instanceof Error ? error.message : String(error)); }
  }

  async function runImport(previewOnly: boolean) {
    if (!file) return;
    try {
      const next = await importTargets(projectId, file, previewOnly);
      setResult(next);
      setMessage(previewOnly ? t('planner.import.previewReady', { errors: next.errors }) : t('planner.import.applied', { count: next.applied }));
      if (!previewOnly) { await load(); await onChanged(); }
    } catch (error) { setMessage(error instanceof Error ? error.message : String(error)); }
  }

  return <>
    <section className="teams-card planner-form"><h2>{t('planner.targets.editTitle')}</h2>
      <p>{t('planner.targets.editHint')}</p>
      <div className="planner-grid">
        <label>{t('planner.month')}<select value={form.month} onChange={(e) => setForm({ ...form, month: Number(e.target.value) })}>{MONTHS.slice(1).map((name, i) => <option key={name} value={i + 1} disabled={closedMonths.includes(i + 1)}>{name}</option>)}</select></label>
        <label>{t('planner.municipality')}<input value={form.municipality} onChange={(e) => setForm({ ...form, municipality: e.target.value })} /></label>
        <label>{t('planner.activity')}<select value={form.template_id} onChange={(e) => setForm({ ...form, template_id: e.target.value })}><option value="">—</option>{catalog.activities.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}</select></label>
        <label>{t('planner.gestorOptional')}<select value={form.gestor_user_id} onChange={(e) => setForm({ ...form, gestor_user_id: e.target.value })}><option value="">{t('planner.wholeMunicipality')}</option>{catalog.people.map((p) => <option key={p.id} value={p.id}>{p.full_name}</option>)}</select></label>
        <label>{t('planner.unit')}<select value={form.unit} onChange={(e) => setForm({ ...form, unit: e.target.value as 'records' | 'families' })}><option value="records">{t('planner.unitRecords')}</option><option value="families">{t('planner.unitFamilies')}</option></select></label>
        <label>{t('planner.goal')}<input type="number" min={0} value={form.target} onChange={(e) => setForm({ ...form, target: Math.max(0, Math.trunc(Number(e.target.value) || 0)) })} /></label>
        <label className="planner-wide">{t('planner.reason')}<input value={form.reason} placeholder={t('planner.reasonHint')} onChange={(e) => setForm({ ...form, reason: e.target.value })} /></label>
      </div>
      <button type="button" disabled={!form.template_id} onClick={() => void save()}>{t('planner.targets.save')}</button>
    </section>
    <section className="teams-card planner-form"><h2>{t('planner.import.title')}</h2>
      <p>{t('planner.import.hint')}</p>
      <div className="planner-actions">
        <button type="button" className="secondary" onClick={() => void downloadTemplate()}>{t('planner.import.template')}</button>
        <input type="file" accept=".csv,.xlsx" aria-label={t('planner.import.file')} onChange={(e) => { setFile(e.target.files?.[0] ?? null); setResult(null); }} />
        <button type="button" disabled={!file} onClick={() => void runImport(true)}>{t('planner.import.validate')}</button>
        <button type="button" disabled={!file || !result || result.errors > 0} onClick={() => void runImport(false)}>{t('planner.import.apply')}</button>
        {file && result && result.errors > 0 ? <button type="button" className="secondary" onClick={() => void downloadImportErrors(projectId, file)}>{t('planner.import.errors')}</button> : null}
      </div>
      {result ? <><p>{t('planner.import.impact', { before: result.total_before, after: result.total_after })}</p>
        <div className="records-table-wrap"><table className="records-table"><thead><tr><th>{t('planner.import.row')}</th><th>{t('planner.state')}</th><th>{t('planner.municipality')}</th><th>{t('planner.activity')}</th><th>{t('planner.before')}</th><th>{t('planner.after')}</th><th>{t('planner.detail')}</th></tr></thead>
          <tbody>{result.rows.map((row) => <tr key={row.row} className={row.status === 'error' || row.status === 'exists' ? 'planner-row-error' : ''}><td>{row.row}</td><td>{t(`planner.import.status.${row.status}`)}</td><td>{row.municipality ?? ''}</td><td>{row.template ?? ''}</td><td>{row.before ?? '—'}</td><td>{row.after ?? '—'}</td><td>{row.message}</td></tr>)}</tbody></table></div></> : null}
    </section>
    {message ? <p role="status">{message}</p> : null}
    <section className="teams-card"><h2>{t('planner.targets.listTitle', { year })}</h2>
      <div className="records-table-wrap"><table className="records-table"><thead><tr><th>{t('planner.month')}</th><th>{t('planner.municipality')}</th><th>{t('planner.activity')}</th><th>{t('planner.gestor')}</th><th>{t('planner.unit')}</th><th>{t('planner.goal')}</th><th>{t('planner.version')}</th></tr></thead>
        <tbody>{rows.map((row) => <tr key={row.id}><td>{MONTHS[row.month]}</td><td>{row.municipality || '—'}</td><td>{activityName.get(row.template_id) ?? row.template_id}</td><td>{row.gestor_user_id ? personName.get(row.gestor_user_id) ?? row.gestor_user_id : t('planner.wholeMunicipality')}</td><td>{row.unit === 'records' ? t('planner.unitRecords') : t('planner.unitFamilies')}</td><td>{row.target}</td><td>{row.version}</td></tr>)}
          {!rows.length && <tr><td colSpan={7}>{t('planner.empty')}</td></tr>}</tbody></table></div>
    </section>
  </>;
}

function Plans({ projectId, year, catalog, activityName, personName, onChanged }: { projectId: string; year: number; catalog: PlannerCatalog; activityName: Map<string, string>; personName: Map<string, string>; onChanged: () => Promise<void> }) {
  const { t } = useI18n();
  const [rows, setRows] = useState<PlannerPlan[]>([]);
  const [form, setForm] = useState({ template_id: '', gestor_user_id: '', start_date: '', end_date: '', planned_quantity: 0, planned_participants: 0, note: '' });
  const [message, setMessage] = useState('');
  const load = () => fetchPlans(projectId, year).then(setRows).catch((error: Error) => setMessage(error.message));
  useEffect(() => { void load(); }, [projectId, year]);

  async function create() {
    try {
      await createPlan(projectId, { ...form, gestor_user_id: form.gestor_user_id || null });
      setForm({ ...form, start_date: '', end_date: '', planned_quantity: 0, planned_participants: 0, note: '' });
      setMessage(t('planner.plans.created')); await load(); await onChanged();
    } catch (error) { setMessage(error instanceof Error ? error.message : String(error)); }
  }

  async function reschedule(plan: PlannerPlan) {
    const start = window.prompt(t('planner.plans.newStart'), plan.start_date);
    if (!start) return;
    const end = window.prompt(t('planner.plans.newEnd'), plan.end_date);
    if (!end) return;
    const reason = window.prompt(t('planner.plans.reason'));
    if (!reason) return;
    try { await reschedulePlan(plan.id, { start_date: start, end_date: end, planned_quantity: plan.planned_quantity, reason }); await load(); await onChanged(); }
    catch (error) { setMessage(error instanceof Error ? error.message : String(error)); }
  }

  async function cancel(plan: PlannerPlan) {
    const reason = window.prompt(t('planner.plans.cancelReason'));
    if (!reason) return;
    try { await cancelPlan(plan.id, reason); await load(); await onChanged(); }
    catch (error) { setMessage(error instanceof Error ? error.message : String(error)); }
  }

  const statusLabel = (status: string) => t(`planner.plans.status.${status}`);
  return <>
    <section className="teams-card planner-form"><h2>{t('planner.plans.newTitle')}</h2>
      <p>{t('planner.plans.hint')}</p>
      <div className="planner-grid">
        <label>{t('planner.activity')}<select value={form.template_id} onChange={(e) => setForm({ ...form, template_id: e.target.value })}><option value="">—</option>{catalog.activities.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}</select></label>
        {catalog.can_manage ? <label>{t('planner.gestor')}<select value={form.gestor_user_id} onChange={(e) => setForm({ ...form, gestor_user_id: e.target.value })}><option value="">{t('planner.plans.me')}</option>{catalog.people.map((p) => <option key={p.id} value={p.id}>{p.full_name}</option>)}</select></label> : null}
        <label>{t('planner.plans.start')}<input type="date" value={form.start_date} onChange={(e) => setForm({ ...form, start_date: e.target.value })} /></label>
        <label>{t('planner.plans.end')}<input type="date" value={form.end_date} onChange={(e) => setForm({ ...form, end_date: e.target.value })} /></label>
        <label>{t('planner.scheduled')}<input type="number" min={0} value={form.planned_quantity} onChange={(e) => setForm({ ...form, planned_quantity: Math.max(0, Math.trunc(Number(e.target.value) || 0)) })} /></label>
        <label>{t('planner.plans.participants')}<input type="number" min={0} value={form.planned_participants} onChange={(e) => setForm({ ...form, planned_participants: Math.max(0, Math.trunc(Number(e.target.value) || 0)) })} /></label>
        <label className="planner-wide">{t('planner.plans.note')}<input value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} /></label>
      </div>
      <button type="button" disabled={!form.template_id || !form.start_date || !form.end_date} onClick={() => void create()}>{t('planner.plans.create')}</button>
    </section>
    {message ? <p role="status">{message}</p> : null}
    <section className="teams-card"><h2>{t('planner.plans.listTitle', { year })}</h2>
      <div className="records-table-wrap"><table className="records-table"><thead><tr><th>{t('planner.gestor')}</th><th>{t('planner.activity')}</th><th>{t('planner.municipality')}</th><th>{t('planner.plans.dates')}</th><th>{t('planner.scheduled')}</th><th>{t('planner.state')}</th><th /></tr></thead>
        <tbody>{rows.map((row) => <tr key={row.id}><td>{personName.get(row.gestor_user_id) ?? row.gestor_user_id}</td><td>{activityName.get(row.template_id) ?? row.template_id}</td><td>{row.municipality || '—'}</td><td>{row.start_date} → {row.end_date}</td><td>{row.planned_quantity}</td><td>{statusLabel(row.status)}</td>
          <td>{row.status !== 'cancelled' ? <><button type="button" className="secondary" onClick={() => void reschedule(row)}>{t('planner.plans.reschedule')}</button> <button type="button" className="secondary" onClick={() => void cancel(row)}>{t('planner.plans.cancel')}</button></> : null}</td></tr>)}
          {!rows.length && <tr><td colSpan={7}>{t('planner.empty')}</td></tr>}</tbody></table></div>
    </section>
  </>;
}

function Population({ projectId, year, onChanged }: { projectId: string; year: number; onChanged: () => Promise<void> }) {
  const { t } = useI18n();
  const [rows, setRows] = useState<PlannerPopulation[]>([]);
  const [form, setForm] = useState({ municipality: '', families: 0, participants: 0, source: '', reason: '' });
  const [message, setMessage] = useState('');
  const load = () => fetchPopulation(projectId, year).then(setRows).catch((error: Error) => setMessage(error.message));
  useEffect(() => { void load(); }, [projectId, year]);
  async function save() {
    try { await savePopulation(projectId, { year, ...form }); setMessage(t('planner.population.saved')); await load(); await onChanged(); }
    catch (error) { setMessage(error instanceof Error ? error.message : String(error)); }
  }
  return <>
    <section className="teams-card planner-form"><h2>{t('planner.population.title', { year })}</h2>
      <p>{t('planner.population.hint')}</p>
      <div className="planner-grid">
        <label>{t('planner.municipality')}<input value={form.municipality} onChange={(e) => setForm({ ...form, municipality: e.target.value })} /></label>
        <label>{t('planner.population.families')}<input type="number" min={0} value={form.families} onChange={(e) => setForm({ ...form, families: Math.max(0, Math.trunc(Number(e.target.value) || 0)) })} /></label>
        <label>{t('planner.population.participants')}<input type="number" min={0} value={form.participants} onChange={(e) => setForm({ ...form, participants: Math.max(0, Math.trunc(Number(e.target.value) || 0)) })} /></label>
        <label>{t('planner.population.source')}<input value={form.source} onChange={(e) => setForm({ ...form, source: e.target.value })} /></label>
        <label className="planner-wide">{t('planner.reason')}<input value={form.reason} placeholder={t('planner.reasonHint')} onChange={(e) => setForm({ ...form, reason: e.target.value })} /></label>
      </div>
      <button type="button" disabled={!form.municipality} onClick={() => void save()}>{t('planner.population.save')}</button>
    </section>
    {message ? <p role="status">{message}</p> : null}
    <section className="teams-card"><div className="records-table-wrap"><table className="records-table"><thead><tr><th>{t('planner.municipality')}</th><th>{t('planner.population.families')}</th><th>{t('planner.population.participants')}</th><th>{t('planner.population.source')}</th><th>{t('planner.version')}</th></tr></thead>
      <tbody>{rows.map((row) => <tr key={row.id}><td>{row.municipality}</td><td>{row.families}</td><td>{row.participants}</td><td>{row.source ?? '—'}</td><td>{row.version}</td></tr>)}
        {!rows.length && <tr><td colSpan={5}>{t('planner.empty')}</td></tr>}</tbody></table></div></section>
  </>;
}

function Settings({ projectId, onChanged }: { projectId: string; onChanged: () => Promise<void> }) {
  const { t } = useI18n();
  const [settings, setSettings] = useState<PlannerSettings | null>(null);
  const [reason, setReason] = useState('');
  const [message, setMessage] = useState('');
  useEffect(() => { void fetchSettings(projectId).then(setSettings).catch((error: Error) => setMessage(error.message)); }, [projectId]);
  if (!settings) return <p>{message || t('planner.loading')}</p>;
  async function save() {
    if (!settings) return;
    try { setSettings(await saveSettings(projectId, { ...settings, reason })); setMessage(t('planner.settings.saved')); await onChanged(); }
    catch (error) { setMessage(error instanceof Error ? error.message : String(error)); }
  }
  return <section className="teams-card planner-form"><h2>{t('planner.settings.title')}</h2>
    <div className="planner-grid">
      <label>{t('planner.settings.countPolicy')}<select value={settings.count_policy} onChange={(e) => setSettings({ ...settings, count_policy: e.target.value as PlannerSettings['count_policy'] })}>
        <option value="approved">{t('planner.settings.approved')}</option><option value="submitted">{t('planner.settings.submitted')}</option></select></label>
      <label>{t('planner.settings.familyKey')}<select value={settings.family_key} onChange={(e) => setSettings({ ...settings, family_key: e.target.value as PlannerSettings['family_key'] })}>
        <option value="participant">{t('planner.settings.keyParticipant')}</option><option value="document_id">{t('planner.settings.keyDocument')}</option>
        <option value="external_code">{t('planner.settings.keyCode')}</option><option value="field">{t('planner.settings.keyField')}</option></select></label>
      {settings.family_key === 'field' ? <label>{t('planner.settings.familyField')}<input value={settings.family_field ?? ''} placeholder="codigo_hogar" onChange={(e) => setSettings({ ...settings, family_field: e.target.value })} /></label> : null}
      <label>{t('planner.settings.dateField')}<input value={settings.activity_date_field ?? ''} placeholder={t('planner.settings.dateFieldHint')} onChange={(e) => setSettings({ ...settings, activity_date_field: e.target.value })} /></label>
      <label>{t('planner.settings.municipalityField')}<input value={settings.municipality_field ?? ''} placeholder="municipio" onChange={(e) => setSettings({ ...settings, municipality_field: e.target.value })} /></label>
      <label>{t('planner.settings.timezone')}<input value={settings.timezone} onChange={(e) => setSettings({ ...settings, timezone: e.target.value })} /></label>
      <label className="planner-wide">{t('planner.reason')}<input value={reason} onChange={(e) => setReason(e.target.value)} /></label>
    </div>
    <p className="planner-hint">{t('planner.settings.hint')}</p>
    <button type="button" onClick={() => void save()}>{t('planner.settings.save')}</button>
    {message ? <p role="status">{message}</p> : null}
  </section>;
}
