import { useEffect, useMemo, useState } from 'react';

import { AppShell } from '../../components/AppShell';
import { useI18n } from '../../i18n';
import { PROJECT_KEY } from '../auth/session';
import { analyzeRecord, createAuditConfig, fetchAiProviders, fetchAuditConfig, fetchChecks, saveAiProvider, testAiProvider } from './aiAuditApi';
import type { AiAuditConfig, AiCheck, AiProvider } from './aiAuditApi';

type Tab = 'alerts' | 'config' | 'providers';

function statusClass(status: string) {
  if (status === 'none') return 'sent';
  if (status === 'possible') return 'skipped';
  if (status === 'high' || status === 'error') return 'failed';
  return 'skipped';
}

function parseResult(resultJson?: string | null): { reasoning?: string; flagged_phrases?: string[]; reason?: string; error?: string } {
  if (!resultJson) return {};
  try {
    return JSON.parse(resultJson);
  } catch {
    return {};
  }
}

export function AiAuditApp() {
  const { t } = useI18n();
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';
  const [tab, setTab] = useState<Tab>('alerts');
  const [message, setMessage] = useState('');

  const [checks, setChecks] = useState<AiCheck[]>([]);
  const semanticChecks = useMemo(() => checks.filter((check) => check.check_type === 'semantic_audit'), [checks]);

  const [configTemplateId, setConfigTemplateId] = useState('');
  const [configTextField, setConfigTextField] = useState('');
  const [configMode, setConfigMode] = useState('human');
  const [lookupTemplateId, setLookupTemplateId] = useState('');
  const [lookupResult, setLookupResult] = useState<AiAuditConfig | null | undefined>(undefined);
  const [analyzeRecordId, setAnalyzeRecordId] = useState('');
  const [providers, setProviders] = useState<AiProvider[]>([]);
  const [editingProviderId, setEditingProviderId] = useState('');
  const [providerName, setProviderName] = useState('');
  const [providerKind, setProviderKind] = useState('gemini');
  const [providerModel, setProviderModel] = useState('gemini-2.5-flash-lite');
  const [providerBaseUrl, setProviderBaseUrl] = useState('');
  const [providerKey, setProviderKey] = useState('');
  const [providerStatus, setProviderStatus] = useState<'active' | 'disabled'>('active');
  const [providerBusy, setProviderBusy] = useState(false);

  function statusLabel(status: string) {
    const labels: Record<string, string> = {
      none: t('admin.aiAudit.statusNone'),
      possible: t('admin.aiAudit.statusPossible'),
      high: t('admin.aiAudit.statusHigh'),
      skipped: t('admin.aiAudit.statusSkipped'),
      error: t('admin.aiAudit.statusError'),
    };
    return labels[status] ?? status;
  }

  function modeLabel(mode: string) {
    const labels: Record<string, string> = {
      human: t('admin.aiAudit.modeHuman'),
      automatic: t('admin.aiAudit.modeAutomatic'),
      mixed: t('admin.aiAudit.modeMixed'),
    };
    return labels[mode] ?? mode;
  }

  async function loadChecks() {
    try {
      setChecks(await fetchChecks(projectId));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('admin.aiAudit.errorLoadAlerts'));
    }
  }

  useEffect(() => { void loadChecks(); }, [projectId]);
  useEffect(() => { if (projectId) void fetchAiProviders(projectId).then(setProviders).catch((error: Error) => setMessage(error.message)); }, [projectId]);

  function editProvider(item: AiProvider) {
    setEditingProviderId(item.id); setProviderName(item.name); setProviderKind(item.provider);
    setProviderModel(item.model); setProviderBaseUrl(item.base_url);
    setProviderKey(''); setProviderStatus(item.status); setTab('providers');
  }

  function resetProvider() {
    setEditingProviderId(''); setProviderName(''); setProviderKind('gemini');
    setProviderModel('gemini-2.5-flash-lite'); setProviderBaseUrl('');
    setProviderKey(''); setProviderStatus('active');
  }

  async function submitProvider() {
    setProviderBusy(true);
    try {
      await saveAiProvider({ project_id: projectId, name: providerName, provider: providerKind,
        model: providerModel, base_url: providerBaseUrl, api_key: providerKey, status: providerStatus }, editingProviderId || undefined);
      setProviders(await fetchAiProviders(projectId));
      resetProvider(); setMessage(t('admin.aiAudit.providerSaved'));
    } catch (error) { setMessage(error instanceof Error ? error.message : t('admin.aiAudit.providerError')); }
    finally { setProviderBusy(false); }
  }

  async function toggleProvider(item: AiProvider) {
    try {
      await saveAiProvider({ project_id: projectId, name: item.name, provider: item.provider,
        model: item.model, base_url: item.base_url, api_key: '', status: item.status === 'active' ? 'disabled' : 'active' }, item.id);
      setProviders(await fetchAiProviders(projectId));
    } catch (error) { setMessage(error instanceof Error ? error.message : t('admin.aiAudit.providerError')); }
  }

  async function submitConfig() {
    try {
      await createAuditConfig({ templateId: configTemplateId, textFieldName: configTextField, mode: configMode });
      setMessage(t('admin.aiAudit.templateLinked'));
      setConfigTemplateId('');
      setConfigTextField('');
      setConfigMode('human');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('admin.aiAudit.errorLinkTemplate'));
    }
  }

  async function lookupConfig() {
    try {
      setLookupResult(await fetchAuditConfig(lookupTemplateId.trim()));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('admin.aiAudit.errorLookupConfig'));
    }
  }

  async function submitAnalyze() {
    try {
      const result = await analyzeRecord(analyzeRecordId.trim());
      setMessage(result ? t('admin.aiAudit.analysisCompleted', { status: statusLabel(result.status) }) : t('admin.aiAudit.noSemanticConfig'));
      await loadChecks();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('admin.aiAudit.errorReanalyze'));
    }
  }

  return (
    <AppShell title={t('admin.aiAudit.title')}>
      <main className="audit-shell">
        <nav className="erp-tabs">
          <button className={tab === 'alerts' ? 'active' : undefined} onClick={() => setTab('alerts')}>{t('admin.aiAudit.tabAlerts')}</button>
          <button className={tab === 'config' ? 'active' : undefined} onClick={() => setTab('config')}>{t('admin.aiAudit.tabConfig')}</button>
          <button className={tab === 'providers' ? 'active' : undefined} onClick={() => setTab('providers')}>{t('admin.aiAudit.tabProviders')}</button>
        </nav>
        {message ? <p role="status" className="erp-message">{message}</p> : null}

        {tab === 'alerts' ? (
          <section className="audit-panel">
            <header>
              <div>
                <h2>{t('admin.aiAudit.alertsTitle')}</h2>
                <p>{t('admin.aiAudit.alertsDescription')}</p>
              </div>
              <button onClick={() => void loadChecks()}>{t('admin.aiAudit.refresh')}</button>
            </header>
            <div className="ai-analyze-inline">
              <label>
                {t('admin.aiAudit.reanalyzeLabel')}
                <input value={analyzeRecordId} onChange={(event) => setAnalyzeRecordId(event.target.value)} placeholder="record_id" />
              </label>
              <button disabled={!analyzeRecordId.trim()} onClick={() => void submitAnalyze()}>{t('admin.aiAudit.analyze')}</button>
            </div>
            {!semanticChecks.length ? <p>{t('admin.aiAudit.noChecksYet')}</p> : null}
            <div className="audit-table-wrap">
              <table className="audit-table">
                <thead>
                  <tr>
                    <th>{t('admin.aiAudit.colDate')}</th>
                    <th>{t('admin.aiAudit.colStatus')}</th>
                    <th>{t('admin.aiAudit.colRecord')}</th>
                    <th>{t('admin.aiAudit.colReasoning')}</th>
                    <th>{t('admin.aiAudit.colFlaggedPhrases')}</th>
                  </tr>
                </thead>
                <tbody>
                  {semanticChecks.map((check) => {
                    const result = parseResult(check.result_json);
                    return (
                      <tr key={check.id}>
                        <td>{new Date(check.created_at).toLocaleString()}</td>
                        <td><span className={`wa-status ${statusClass(check.status)}`}>{statusLabel(check.status)}</span></td>
                        <td>{check.record_id ?? '—'}</td>
                        <td>{result.reasoning ?? result.reason ?? result.error ?? '—'}</td>
                        <td>{result.flagged_phrases?.length ? <code>{result.flagged_phrases.join(' · ')}</code> : '—'}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>
        ) : null}

        {tab === 'config' ? (
          <section className="ds-maps">
            <div className="ds-map-create">
              <h2>{t('admin.aiAudit.linkTemplateTitle')}</h2>
              <p>{t('admin.aiAudit.linkTemplateDescription')}</p>
              <label>{t('admin.aiAudit.templateIdLabel')}<input value={configTemplateId} onChange={(event) => setConfigTemplateId(event.target.value)} placeholder="template_id" /></label>
              <label>{t('admin.aiAudit.textFieldLabel')}<input value={configTextField} onChange={(event) => setConfigTextField(event.target.value)} placeholder={t('admin.aiAudit.textFieldPlaceholder')} /></label>
              <label>
                {t('admin.aiAudit.reactionModeLabel')}
                <select value={configMode} onChange={(event) => setConfigMode(event.target.value)}>
                  <option value="human">{t('admin.aiAudit.modeHuman')}</option>
                  <option value="mixed">{t('admin.aiAudit.modeMixed')}</option>
                  <option value="automatic">{t('admin.aiAudit.modeAutomatic')}</option>
                </select>
              </label>
              <button className="primary" disabled={!configTemplateId.trim() || !configTextField.trim()} onClick={() => void submitConfig()}>{t('admin.aiAudit.link')}</button>
            </div>
            <div className="ds-map-list">
              <h2>{t('admin.aiAudit.lookupTitle')}</h2>
              <label>{t('admin.aiAudit.templateIdShort')}<input value={lookupTemplateId} onChange={(event) => setLookupTemplateId(event.target.value)} placeholder="template_id" /></label>
              <button onClick={() => void lookupConfig()}>{t('admin.aiAudit.lookup')}</button>
              {lookupResult === null ? <p>{t('admin.aiAudit.noAuditConfig')}</p> : null}
              {lookupResult ? (
                <article className="ds-map-card">
                  <strong>{t('admin.aiAudit.analyzedField', { field: lookupResult.text_field_name })}</strong>
                  <span>{t('admin.aiAudit.modePrefix', { mode: modeLabel(lookupResult.mode) })}</span>
                  <small>{t('admin.aiAudit.configuredAt', { date: new Date(lookupResult.created_at).toLocaleString() })}</small>
                </article>
              ) : null}
            </div>
          </section>
        ) : null}
        {tab === 'providers' && <section className="audit-panel">
          <h2>{t('admin.aiAudit.providerTitle')}</h2>
          <p>{t('admin.aiAudit.providerHint')}</p>
          <div className="ds-map-create">
            <label>{t('admin.aiAudit.providerName')}<input value={providerName} maxLength={180} onChange={(event) => setProviderName(event.target.value)} /></label>
            <label>{t('admin.aiAudit.providerType')}<select value={providerKind} onChange={(event) => { const kind = event.target.value; setProviderKind(kind); setProviderModel(kind === 'gemini' ? 'gemini-2.5-flash-lite' : ''); }}>
              {['gemini', 'openai', 'anthropic', 'openrouter', 'deepseek', 'groq', 'custom'].map((kind) => <option key={kind} value={kind}>{kind === 'custom' ? t('admin.aiAudit.providerCustom') : kind}</option>)}
            </select></label>
            <label>{t('admin.aiAudit.providerModel')}<input value={providerModel} maxLength={120} onChange={(event) => setProviderModel(event.target.value)} placeholder="gemini-2.5-flash-lite" /></label>
            {providerKind === 'custom' && <label>{t('admin.aiAudit.providerUrl')}<input type="url" value={providerBaseUrl} onChange={(event) => setProviderBaseUrl(event.target.value)} placeholder="https://api.example.com/v1" /></label>}
            <label>{t('admin.aiAudit.providerKey')}<input type="password" autoComplete="new-password" value={providerKey} onChange={(event) => setProviderKey(event.target.value)} placeholder={editingProviderId ? t('admin.aiAudit.providerKeepKey') : ''} /></label>
            <label>{t('admin.aiAudit.providerStatus')}<select value={providerStatus} onChange={(event) => setProviderStatus(event.target.value as 'active' | 'disabled')}><option value="active">{t('admin.aiAudit.providerActive')}</option><option value="disabled">{t('admin.aiAudit.providerDisabled')}</option></select></label>
            <div><button type="button" disabled={providerBusy || !providerName.trim() || !providerModel.trim() || (!editingProviderId && !providerKey.trim())} onClick={() => void submitProvider()}>{t('app.save')}</button>{editingProviderId && <button type="button" onClick={resetProvider}>{t('app.cancel')}</button>}</div>
          </div>
          <div className="ds-map-list">{providers.map((item) => <article className="ds-map-card" key={item.id}><strong>{item.name}</strong><span>{item.provider} · {item.model} · {item.status === 'active' ? t('admin.aiAudit.providerActive') : t('admin.aiAudit.providerDisabled')}</span><small>{item.has_key ? t('admin.aiAudit.providerKeySaved') : t('admin.aiAudit.providerKeyMissing')}</small><div><button type="button" onClick={() => editProvider(item)}>{t('admin.aiAudit.providerEdit')}</button><button type="button" onClick={() => void toggleProvider(item)}>{item.status === 'active' ? t('admin.aiAudit.providerDisable') : t('admin.aiAudit.providerEnable')}</button><button type="button" disabled={item.status !== 'active'} onClick={() => void testAiProvider(projectId, item.id).then(() => setMessage(t('admin.aiAudit.providerConnected'))).catch((error: Error) => setMessage(error.message))}>{t('admin.aiAudit.providerTest')}</button></div></article>)}</div>
        </section>}
      </main>
    </AppShell>
  );
}
