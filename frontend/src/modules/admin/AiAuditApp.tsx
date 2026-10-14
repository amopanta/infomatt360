import { useEffect, useMemo, useState } from 'react';

import { AppShell } from '../../components/AppShell';
import { useI18n } from '../../i18n';
import { PROJECT_KEY } from '../auth/session';
import { analyzeRecord, createAuditConfig, fetchAuditConfig, fetchChecks } from './aiAuditApi';
import type { AiAuditConfig, AiCheck } from './aiAuditApi';

type Tab = 'alerts' | 'config';

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
      </main>
    </AppShell>
  );
}
