import { useEffect, useState } from 'react';

import { AppShell } from '../../components/AppShell';
import { useI18n } from '../../i18n';
import { PROJECT_KEY } from '../auth/session';
import { fetchProjectTemplates } from '../records/api';
import type { TemplateSummary } from '../records/api';
import { approveExcelImport, confirmExcelImportMapping, downloadExcelImportTemplate, fetchExcelImportJobs, uploadExcelImport, validateExcelImport } from './excelImportApi';
import type { ExcelImportJob, ExcelImportTargetField, ExcelImportValidation } from './excelImportApi';

const TARGET_FIELDS: Record<string, string[]> = {
  participants: ['document_id', 'full_name', 'external_code', 'participant_type', 'department', 'municipality'],
  participant_updates: ['document_id', 'full_name', 'external_code', 'participant_type', 'department', 'municipality', 'group_name', 'status'],
  users: ['document_id', 'full_name', 'email', 'phone', 'position', 'department', 'municipality', 'role_name', 'restrict_to_territory'],
  assignments: ['email', 'role_name', 'status'],
};

// Etiquetas legibles de los campos destino (docs/145).
const FIELD_LABELS: Record<string, string> = {
  document_id: 'Número de documento', full_name: 'Nombre completo', email: 'Correo', phone: 'Teléfono', position: 'Cargo',
  department: 'Departamento', municipality: 'Municipio', role_name: 'Rol', restrict_to_territory: 'Limitar acceso (sí/no)', status: 'Estado',
};

function statusClass(status: string) {
  if (status === 'completed') return 'sent';
  if (status === 'failed') return 'failed';
  return 'skipped';
}

export function ExcelImportApp() {
  const { t } = useI18n();
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';
  // ?tipo=users abre la carga con ese tipo elegido (enlace desde Usuarios, docs/145).
  const [entityType, setEntityType] = useState(() => {
    const requested = new URLSearchParams(window.location.search).get('tipo') ?? '';
    return ['participants', 'participant_updates', 'users', 'assignments', 'records'].includes(requested) ? requested : 'participants';
  });
  const [templates, setTemplates] = useState<TemplateSummary[]>([]);
  const [templateId, setTemplateId] = useState('');
  const [groupName, setGroupName] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [currentJob, setCurrentJob] = useState<ExcelImportJob | null>(null);
  const [columnMapping, setColumnMapping] = useState<Record<string, string>>({});
  const [jobs, setJobs] = useState<ExcelImportJob[]>([]);
  const [message, setMessage] = useState('');
  const [validation, setValidation] = useState<ExcelImportValidation | null>(null);
  const [busy, setBusy] = useState(false);

  function statusLabel(status: string) {
    const labels: Record<string, string> = {
      uploaded: t('admin.excelImport.statusUploaded'),
      mapped: t('admin.excelImport.statusMapped'),
      completed: t('admin.excelImport.statusCompleted'),
      failed: t('admin.excelImport.statusFailed'),
    };
    return labels[status] ?? status;
  }

  async function loadJobs() {
    try {
      setJobs(await fetchExcelImportJobs(projectId));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('admin.excelImport.errorLoadJobs'));
    }
  }

  useEffect(() => { void loadJobs(); }, [projectId]);

  useEffect(() => {
    if (entityType !== 'records' || !projectId) return;
    fetchProjectTemplates(projectId)
      .then(setTemplates)
      .catch((error: Error) => setMessage(error.message));
  }, [entityType, projectId]);

  async function submitUpload() {
    if (!file) return;
    if (entityType === 'participants' && !groupName.trim()) { setMessage(t('admin.excelImport.groupRequired')); return; }
    if (entityType === 'records' && !templateId) {
      setMessage(t('admin.excelImport.templateRequired'));
      return;
    }
    setBusy(true);
    try {
      const job = await uploadExcelImport({ projectId, entityType, templateId: entityType === 'records' ? templateId : undefined, groupName: entityType === 'participants' ? groupName.trim() : undefined, file });
      setCurrentJob(job);
      setValidation(null);
      setColumnMapping(job.column_mapping ?? {});
      setMessage(t('admin.excelImport.rowsDetected', { count: job.total_rows }));
      await loadJobs();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('admin.excelImport.errorUpload'));
    } finally {
      setBusy(false);
    }
  }

  async function submitMapping() {
    if (!currentJob) return;
    setBusy(true);
    try {
      const mapping = Object.fromEntries(Object.entries(columnMapping).filter(([, target]) => target));
      const job = await confirmExcelImportMapping(currentJob.id, mapping);
      setCurrentJob(job);
      setValidation(null);
      setMessage(t('admin.excelImport.mappingConfirmed'));
      await loadJobs();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('admin.excelImport.errorConfirmMapping'));
    } finally {
      setBusy(false);
    }
  }

  async function submitApprove() {
    if (!currentJob) return;
    if (!validation || validation.errors.length) { setMessage(t('admin.excelImport.validateFirst')); return; }
    setBusy(true);
    try {
      const job = await approveExcelImport(currentJob.id);
      setCurrentJob(job);
      setMessage(t('admin.excelImport.importResult', { imported: job.imported_rows, failed: job.failed_rows }));
      await loadJobs();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('admin.excelImport.errorApprove'));
    } finally {
      setBusy(false);
    }
  }

  async function submitValidation() {
    if (!currentJob) return;
    setBusy(true);
    try { const result = await validateExcelImport(currentJob.id); setValidation(result); setMessage(t('admin.excelImport.validationResult', { valid: result.valid_rows, total: result.total_rows, errors: result.errors.length })); }
    catch (error) { setMessage(error instanceof Error ? error.message : t('admin.excelImport.errorValidate')); }
    finally { setBusy(false); }
  }

  const dynamicTargetFields: ExcelImportTargetField[] | null = currentJob?.target_fields ?? null;
  const targetFieldOptions: ExcelImportTargetField[] = dynamicTargetFields ?? (TARGET_FIELDS[entityType] ?? []).map((name) => ({ name, label: FIELD_LABELS[name] ? `${FIELD_LABELS[name]} (${name})` : name }));

  return (
    <AppShell title={t('admin.excelImport.title')}>
      <main className="audit-shell">
        {message ? <p role="status" className="erp-message">{message}</p> : null}

        <section className="audit-panel">
          <header>
            <div>
              <h2>{t('admin.excelImport.stepUpload')}</h2>
              <p>{t('admin.excelImport.uploadDescription')}</p>
            </div>
          </header>
          <div className="ai-analyze-inline">
            <label>
              {t('admin.excelImport.entityTypeLabel')}
              <select value={entityType} onChange={(event) => { setEntityType(event.target.value); setTemplateId(''); setValidation(null); }}>
                <option value="participants">{t('admin.excelImport.entityParticipants')}</option>
                <option value="participant_updates">{t('admin.excelImport.entityParticipantUpdates')}</option>
                <option value="users">{t('admin.excelImport.entityUsers')}</option>
                <option value="assignments">{t('admin.excelImport.entityAssignments')}</option>
                <option value="records">{t('admin.excelImport.entityRecords')}</option>
              </select>
            </label>
            {entityType === 'records' ? (
              <label>
                {t('admin.excelImport.formTemplateLabel')}
                <select value={templateId} onChange={(event) => setTemplateId(event.target.value)}>
                  <option value="">{t('admin.excelImport.selectTemplate')}</option>
                  {templates.map((template) => <option key={template.id} value={template.id}>{template.name}</option>)}
                </select>
              </label>
            ) : null}
            {entityType === 'participants' && <label>{t('admin.excelImport.groupNameLabel')}<input value={groupName} maxLength={160} placeholder={t('admin.excelImport.groupNamePlaceholder')} onChange={(event) => setGroupName(event.target.value)} required /><small>{t('admin.excelImport.groupNameHint')}</small></label>}
            {entityType === 'participant_updates' && <p>{t('admin.excelImport.participantUpdateHint')}</p>}
            <button type="button" disabled={busy || (entityType === 'records' && !templateId)} onClick={() => void downloadExcelImportTemplate(projectId, entityType, entityType === 'records' ? templateId : undefined).catch((error: Error) => setMessage(error.message))}>⬇ {t('admin.excelImport.downloadTemplate')}</button>
            <label>
              {t('admin.excelImport.fileLabel')}
              <input type="file" accept=".xlsx" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
            </label>
            <button disabled={!file || busy || (entityType === 'participants' && !groupName.trim())} onClick={() => void submitUpload()}>{t('admin.excelImport.uploadAndPreview')}</button>
          </div>
        </section>

        {currentJob?.preview ? (
          <section className="audit-panel">
            <header>
              <div>
                <h2>{t('admin.excelImport.stepMapping')}</h2>
                <p>{currentJob.source_filename} · {currentJob.total_rows} fila(s) {currentJob.group_name ? `· ${t('admin.excelImport.groupPrefix', { name: currentJob.group_name })}` : ''} · estado: <span className={`wa-status ${statusClass(currentJob.status)}`}>{statusLabel(currentJob.status)}</span></p>
              </div>
            </header>
            <div className="audit-table-wrap">
              <table className="audit-table">
                <thead>
                  <tr>
                    <th>{t('admin.excelImport.colExcelColumn')}</th>
                    <th>{t('admin.excelImport.colTargetField')}</th>
                    {currentJob.preview.sample_rows.slice(0, 2).map((_, index) => <th key={index}>{t('admin.excelImport.examplePrefix', { index: index + 1 })}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {currentJob.preview.headers.map((header) => (
                    <tr key={header}>
                      <td>{header}</td>
                      <td>
                        <select
                          value={columnMapping[header] ?? ''}
                          onChange={(event) => { setValidation(null); setColumnMapping((previous) => ({ ...previous, [header]: event.target.value })); }}
                        >
                          <option value="">{t('admin.excelImport.ignoreOption')}</option>
                          {targetFieldOptions.map((field) => <option key={field.name} value={field.name}>{field.label}</option>)}
                        </select>
                      </td>
                      {currentJob.preview!.sample_rows.slice(0, 2).map((row, index) => (
                        <td key={index}>{String(row[header] ?? '—')}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {currentJob.status === 'uploaded' ? (
              <button className="primary" disabled={busy} onClick={() => void submitMapping()}>{t('admin.excelImport.confirmMapping')}</button>
            ) : null}
            {currentJob.status === 'mapped' ? (
              <><button type="button" disabled={busy} onClick={() => void submitValidation()}>{t('admin.excelImport.validateFile')}</button>{validation && <div role="status"><strong>{t('admin.excelImport.validRowsOf', { valid: validation.valid_rows, total: validation.total_rows })}</strong>{validation.errors.map((error, index) => <p key={index}>{t('admin.excelImport.rowError', { row: error.row, error: error.error })}</p>)}</div>}<button className="primary" disabled={busy || !validation || !!validation.errors.length} onClick={() => void submitApprove()}>{t('admin.excelImport.approveAndImport')}</button></>
            ) : null}
            {currentJob.status === 'completed' || currentJob.status === 'failed' ? (
              <article className="ds-map-card">
                <strong>{t('admin.excelImport.importedLabel', { imported: currentJob.imported_rows })} · {t('admin.excelImport.failedLabel', { failed: currentJob.failed_rows })}</strong>
                {currentJob.error_report?.length ? (
                  <ul>
                    {currentJob.error_report.map((error, index) => <li key={index}>{JSON.stringify(error)}</li>)}
                  </ul>
                ) : null}
              </article>
            ) : null}
          </section>
        ) : null}

        <section className="audit-panel">
          <header>
            <div>
              <h2>{t('admin.excelImport.batchHistory')}</h2>
            </div>
            <button onClick={() => void loadJobs()}>{t('admin.excelImport.refresh')}</button>
          </header>
          {!jobs.length ? <p>{t('admin.excelImport.noBatchesYet')}</p> : null}
          <div className="audit-table-wrap">
            <table className="audit-table">
              <thead>
                <tr>
                  <th>{t('admin.excelImport.colDate')}</th>
                  <th>{t('admin.excelImport.colFile')}</th>
                  <th>{t('admin.excelImport.colType')}</th>
                  <th>{t('admin.excelImport.colStatus')}</th>
                  <th>{t('admin.excelImport.colImportedFailed')}</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((job) => (
                  <tr key={job.id}>
                    <td>{new Date(job.created_at).toLocaleString()}</td>
                    <td>{job.source_filename}</td>
                    <td>{job.entity_type}</td>
                    <td><span className={`wa-status ${statusClass(job.status)}`}>{statusLabel(job.status)}</span></td>
                    <td>{job.imported_rows} / {job.failed_rows}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </main>
    </AppShell>
  );
}
