import { useEffect, useRef, useState } from 'react';

import { AppShell } from '../../components/AppShell';
import { useI18n } from '../../i18n';
import { PROJECT_KEY } from '../auth/session';
import { fetchProjectTemplates } from '../records/api';
import type { TemplateSummary } from '../records/api';
import { downloadMasterTemplate, exportXlsform, importXlsform, listFormVersions, previewXlsform, restoreFormVersion } from './xlsformApi';
import type { FormVersionSummary, XlsformPreview } from './xlsformApi';

export function XlsformApp() {
  const { t } = useI18n();
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';
  const [templates, setTemplates] = useState<TemplateSummary[]>([]);
  const [exportTemplateId, setExportTemplateId] = useState(new URLSearchParams(window.location.search).get('export') ?? '');
  const [replaceTemplateId, setReplaceTemplateId] = useState(new URLSearchParams(window.location.search).get('replace') ?? '');
  const [message, setMessage] = useState('');
  const [importing, setImporting] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [downloadingMaster, setDownloadingMaster] = useState(false);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [preview, setPreview] = useState<XlsformPreview | null>(null);
  const [versions, setVersions] = useState<FormVersionSummary[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  async function loadTemplates() {
    try {
      const rows = await fetchProjectTemplates(projectId);
      setTemplates(rows);
      if (rows.length && !exportTemplateId) setExportTemplateId(rows[0].id);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('admin.xlsform.queryError'));
    }
  }

  useEffect(() => { void loadTemplates(); }, [projectId]);
  useEffect(() => { if (replaceTemplateId) listFormVersions(replaceTemplateId).then(setVersions).catch((error: Error) => setMessage(error.message)); else setVersions([]); }, [replaceTemplateId]);

  async function submitPreview() {
    const file = fileInputRef.current?.files?.[0];
    if (!file) { setMessage(t('admin.xlsform.selectFile')); return; }
    setImporting(true); setMessage(''); setPreview(null);
    try { const result = await previewXlsform(projectId, file, replaceTemplateId || undefined); setPreview(result); setMessage(result.errors.length ? t('admin.xlsform.validationErrors') : t('admin.xlsform.validationComplete')); }
    catch (error) { setMessage(error instanceof Error ? error.message : t('admin.xlsform.validationError')); }
    finally { setImporting(false); }
  }

  async function submitImport() {
    const file = fileInputRef.current?.files?.[0];
    if (!file) {
      setMessage(t('admin.xlsform.selectFileBeforeImport'));
      return;
    }
    if (replaceTemplateId && (!preview || preview.errors.length)) { setMessage(t('admin.xlsform.validateBeforeReplace')); return; }
    setImporting(true);
    setWarnings([]);
    try {
      const result = await importXlsform(projectId, file, replaceTemplateId || undefined, preview ?? undefined);
      setMessage(
        result.replaced
          ? t('admin.xlsform.templateReplaced', { fields: result.imported_fields })
          : t('admin.xlsform.templateImported', { fields: result.imported_fields }),
      );
      setWarnings(result.warnings);
      setPreview(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
      await loadTemplates();
      if (replaceTemplateId) setVersions(await listFormVersions(replaceTemplateId));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('admin.xlsform.importError'));
    } finally {
      setImporting(false);
    }
  }

  async function restore(versionId: string) {
    if (!replaceTemplateId || !window.confirm(t('admin.xlsform.restoreConfirm'))) return;
    setImporting(true); setMessage('');
    try { await restoreFormVersion(replaceTemplateId, versionId); setVersions(await listFormVersions(replaceTemplateId)); setPreview(null); setMessage(t('admin.xlsform.versionRestored')); }
    catch (error) { setMessage(error instanceof Error ? error.message : t('admin.xlsform.restoreError')); }
    finally { setImporting(false); }
  }

  async function submitDownloadMasterTemplate() {
    setDownloadingMaster(true);
    try {
      await downloadMasterTemplate(projectId);
      setMessage(t('admin.xlsform.masterDownloadStarted'));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('admin.xlsform.masterDownloadError'));
    } finally {
      setDownloadingMaster(false);
    }
  }

  async function submitExport() {
    const template = templates.find((item) => item.id === exportTemplateId);
    if (!template) return;
    setExporting(true);
    try {
      await exportXlsform(template.id, template.name);
      setMessage(t('admin.xlsform.exportStarted'));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('admin.xlsform.exportError'));
    } finally {
      setExporting(false);
    }
  }

  return (
    <AppShell title={t('admin.xlsform.title')}>
      <main className="audit-shell">
        {message ? <p role="status" className="erp-message">{message}</p> : null}

        <section className="audit-panel">
          <header>
            <div>
              <h2>{t('admin.xlsform.importTitle')}</h2>
              <p>{t('admin.xlsform.importDescription')}</p>
            </div>
          </header>
          <div className="ai-analyze-inline">
            <input ref={fileInputRef} type="file" accept=".xlsx" onChange={() => setPreview(null)} />
            <label>{t('admin.xlsform.destinationLabel')}
              <select value={replaceTemplateId} onChange={(event) => { setReplaceTemplateId(event.target.value); setPreview(null); }}>
                <option value="">{t('admin.xlsform.createNewTemplate')}</option>
                {templates.map((template) => <option key={template.id} value={template.id}>{t('admin.xlsform.replaceOption', { name: template.name, status: template.status })}</option>)}
              </select>
            </label>
            <button disabled={importing} onClick={() => void submitPreview()}>{t('admin.xlsform.validateAndCompare')}</button>
            <button className="primary" disabled={importing || (replaceTemplateId !== '' && (!preview || !!preview.errors.length))} onClick={() => void submitImport()}>
              {importing ? t('admin.xlsform.importing') : replaceTemplateId ? t('admin.xlsform.replaceInPlace') : t('admin.xlsform.importButton')}
            </button>
            <button disabled={downloadingMaster} onClick={() => void submitDownloadMasterTemplate()}>
              {downloadingMaster ? t('admin.xlsform.generatingMaster') : t('admin.xlsform.downloadMasterTemplate')}
            </button>
          </div>
          {preview && <article className="ds-map-card"><h3>{t('admin.xlsform.comparisonTitle')}</h3><p>{t('admin.xlsform.comparisonSummary', { added: preview.added.length, removed: preview.removed.length, modified: preview.modified.length })}</p>{preview.added.length > 0 && <p><strong>{t('admin.xlsform.newFields')}</strong> {preview.added.join(', ')}</p>}{preview.removed.length > 0 && <p><strong>{t('admin.xlsform.removedFields')}</strong> {preview.removed.join(', ')}</p>}{preview.modified.map((item) => <p key={item.name}><strong>{item.name}:</strong> {item.changes.join(', ')}</p>)}{preview.errors.map((error, index) => <p role="alert" key={index}>{error}</p>)}{preview.warnings.map((warning, index) => <p key={index}>{warning}</p>)}</article>}
          <small>{t('admin.xlsform.masterTemplateHint')}</small>
          {replaceTemplateId ? (
            <small>{t('admin.xlsform.replaceHint')}</small>
          ) : null}
          {warnings.length ? (
            <article className="ds-map-card">
              <strong>{t('admin.xlsform.importWarnings')}</strong>
              <ul>
                {warnings.map((warning, index) => <li key={index}>{warning}</li>)}
              </ul>
            </article>
          ) : null}
          {replaceTemplateId && <article className="ds-map-card"><h3>{t('admin.xlsform.versionHistoryTitle')}</h3>{versions.length ? versions.map((version) => <div key={version.id} className="forms-version-row"><span>{t('admin.xlsform.versionRow', { version: version.version_number, questions: version.question_count, date: new Date(version.created_at).toLocaleString('es-CO') })}</span><button type="button" disabled={importing} onClick={() => void restore(version.id)}>{t('admin.xlsform.restoreVersion')}</button></div>) : <p>{t('admin.xlsform.noVersions')}</p>}</article>}
        </section>

        <section className="audit-panel">
          <header>
            <div>
              <h2>{t('admin.xlsform.exportTitle')}</h2>
              <p>{t('admin.xlsform.exportDescription')}</p>
            </div>
          </header>
          <div className="ai-analyze-inline">
            <label>{t('admin.xlsform.formLabel')}
              <select value={exportTemplateId} onChange={(event) => setExportTemplateId(event.target.value)}>
                {templates.map((template) => <option key={template.id} value={template.id}>{template.name} ({template.status})</option>)}
              </select>
            </label>
            <button className="primary" disabled={exporting || !exportTemplateId} onClick={() => void submitExport()}>
              {exporting ? t('admin.xlsform.generatingExport') : t('admin.xlsform.downloadXlsx')}
            </button>
          </div>
        </section>
      </main>
    </AppShell>
  );
}
