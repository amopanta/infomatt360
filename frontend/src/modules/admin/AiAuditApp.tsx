import { useEffect, useMemo, useState } from 'react';

import { AppShell } from '../../components/AppShell';
import { PROJECT_KEY } from '../auth/session';
import { analyzeRecord, createAuditConfig, fetchAuditConfig, fetchChecks } from './aiAuditApi';
import type { AiAuditConfig, AiCheck } from './aiAuditApi';

type Tab = 'alerts' | 'config';

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    none: 'Sin riesgo',
    possible: 'Posible riesgo',
    high: 'Riesgo alto',
    skipped: 'Omitido (sin proveedor de IA configurado)',
    error: 'Error del proveedor',
  };
  return labels[status] ?? status;
}

function statusClass(status: string) {
  if (status === 'none') return 'sent';
  if (status === 'possible') return 'skipped';
  if (status === 'high' || status === 'error') return 'failed';
  return 'skipped';
}

function modeLabel(mode: string) {
  const labels: Record<string, string> = {
    human: 'Solo alerta (un humano decide)',
    automatic: 'Rechazo automatico ante cualquier riesgo',
    mixed: 'Mixto (rechazo automatico solo en riesgo alto)',
  };
  return labels[mode] ?? mode;
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

  async function loadChecks() {
    try {
      setChecks(await fetchChecks(projectId));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible cargar las alertas.');
    }
  }

  useEffect(() => { void loadChecks(); }, [projectId]);

  async function submitConfig() {
    try {
      await createAuditConfig({ templateId: configTemplateId, textFieldName: configTextField, mode: configMode });
      setMessage('Plantilla vinculada a la auditoria semantica.');
      setConfigTemplateId('');
      setConfigTextField('');
      setConfigMode('human');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible vincular la plantilla.');
    }
  }

  async function lookupConfig() {
    try {
      setLookupResult(await fetchAuditConfig(lookupTemplateId.trim()));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible consultar la configuracion.');
    }
  }

  async function submitAnalyze() {
    try {
      const result = await analyzeRecord(analyzeRecordId.trim());
      setMessage(result ? `Analisis completado: ${statusLabel(result.status)}.` : 'Este registro no tiene una plantilla con auditoria semantica configurada.');
      await loadChecks();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible reanalizar el registro.');
    }
  }

  return (
    <AppShell title="Auditoria semantica con IA">
      <main className="audit-shell">
        <nav className="erp-tabs">
          <button className={tab === 'alerts' ? 'active' : undefined} onClick={() => setTab('alerts')}>Alertas</button>
          <button className={tab === 'config' ? 'active' : undefined} onClick={() => setTab('config')}>Configuracion por plantilla</button>
        </nav>
        {message ? <p role="status" className="erp-message">{message}</p> : null}

        {tab === 'alerts' ? (
          <section className="audit-panel">
            <header>
              <div>
                <h2>Alertas de auditoria semantica</h2>
                <p>Analisis automatico de observaciones de campo en busca de contradicciones o indicios de fraude (ver docs/88).</p>
              </div>
              <button onClick={() => void loadChecks()}>Actualizar</button>
            </header>
            <div className="ai-analyze-inline">
              <label>
                Reanalizar un registro manualmente (ID)
                <input value={analyzeRecordId} onChange={(event) => setAnalyzeRecordId(event.target.value)} placeholder="record_id" />
              </label>
              <button disabled={!analyzeRecordId.trim()} onClick={() => void submitAnalyze()}>Analizar</button>
            </div>
            {!semanticChecks.length ? <p>Aun no hay analisis de auditoria semantica en este proyecto.</p> : null}
            <div className="audit-table-wrap">
              <table className="audit-table">
                <thead>
                  <tr>
                    <th>Fecha</th>
                    <th>Estado</th>
                    <th>Registro</th>
                    <th>Razonamiento</th>
                    <th>Frases senaladas</th>
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
              <h2>Vincular plantilla a la auditoria semantica</h2>
              <p>El campo de texto indicado se analiza automaticamente cada vez que se guarda un registro de esta plantilla.</p>
              <label>ID de la plantilla (Builder)<input value={configTemplateId} onChange={(event) => setConfigTemplateId(event.target.value)} placeholder="template_id" /></label>
              <label>Campo de texto libre a analizar<input value={configTextField} onChange={(event) => setConfigTextField(event.target.value)} placeholder="observaciones" /></label>
              <label>
                Modo de reaccion
                <select value={configMode} onChange={(event) => setConfigMode(event.target.value)}>
                  <option value="human">Solo alerta (un humano decide)</option>
                  <option value="mixed">Mixto (rechazo automatico solo en riesgo alto)</option>
                  <option value="automatic">Rechazo automatico ante cualquier riesgo</option>
                </select>
              </label>
              <button className="primary" disabled={!configTemplateId.trim() || !configTextField.trim()} onClick={() => void submitConfig()}>Vincular</button>
            </div>
            <div className="ds-map-list">
              <h2>Consultar configuracion existente</h2>
              <label>ID de la plantilla<input value={lookupTemplateId} onChange={(event) => setLookupTemplateId(event.target.value)} placeholder="template_id" /></label>
              <button onClick={() => void lookupConfig()}>Consultar</button>
              {lookupResult === null ? <p>Esta plantilla no tiene configuracion de auditoria semantica.</p> : null}
              {lookupResult ? (
                <article className="ds-map-card">
                  <strong>Campo analizado: {lookupResult.text_field_name}</strong>
                  <span>Modo: {modeLabel(lookupResult.mode)}</span>
                  <small>Configurado: {new Date(lookupResult.created_at).toLocaleString()}</small>
                </article>
              ) : null}
            </div>
          </section>
        ) : null}
      </main>
    </AppShell>
  );
}
