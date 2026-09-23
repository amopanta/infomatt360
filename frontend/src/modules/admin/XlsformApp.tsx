import { useEffect, useRef, useState } from 'react';

import { AppShell } from '../../components/AppShell';
import { PROJECT_KEY } from '../auth/session';
import { fetchProjectTemplates } from '../records/api';
import type { TemplateSummary } from '../records/api';
import { downloadMasterTemplate, exportXlsform, importXlsform, listFormVersions, previewXlsform, restoreFormVersion } from './xlsformApi';
import type { FormVersionSummary, XlsformPreview } from './xlsformApi';

export function XlsformApp() {
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
      setMessage(error instanceof Error ? error.message : 'No fue posible consultar los formularios del proyecto.');
    }
  }

  useEffect(() => { void loadTemplates(); }, [projectId]);
  useEffect(() => { if (replaceTemplateId) listFormVersions(replaceTemplateId).then(setVersions).catch((error: Error) => setMessage(error.message)); else setVersions([]); }, [replaceTemplateId]);

  async function submitPreview() {
    const file = fileInputRef.current?.files?.[0];
    if (!file) { setMessage('Selecciona un archivo .xlsx.'); return; }
    setImporting(true); setMessage(''); setPreview(null);
    try { const result = await previewXlsform(projectId, file, replaceTemplateId || undefined); setPreview(result); setMessage(result.errors.length ? 'Corrige los errores antes de aplicar.' : 'Validación completada. Revisa los cambios antes de aplicar.'); }
    catch (error) { setMessage(error instanceof Error ? error.message : 'No se pudo validar el XLSForm.'); }
    finally { setImporting(false); }
  }

  async function submitImport() {
    const file = fileInputRef.current?.files?.[0];
    if (!file) {
      setMessage('Selecciona un archivo .xlsx antes de importar.');
      return;
    }
    if (replaceTemplateId && (!preview || preview.errors.length)) { setMessage('Valida y compara el XLSForm antes de reemplazar.'); return; }
    setImporting(true);
    setWarnings([]);
    try {
      const result = await importXlsform(projectId, file, replaceTemplateId || undefined, preview ?? undefined);
      setMessage(
        result.replaced
          ? `Plantilla reemplazada en el mismo lugar (${result.imported_fields} campo(s)). La estructura anterior quedó respaldada.`
          : `Plantilla importada (${result.imported_fields} campo(s)).`,
      );
      setWarnings(result.warnings);
      setPreview(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
      await loadTemplates();
      if (replaceTemplateId) setVersions(await listFormVersions(replaceTemplateId));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible importar el archivo XLSForm.');
    } finally {
      setImporting(false);
    }
  }

  async function restore(versionId: string) {
    if (!replaceTemplateId || !window.confirm('¿Restaurar esta estructura? La versión actual se guardará en el historial y los registros se conservarán.')) return;
    setImporting(true); setMessage('');
    try { await restoreFormVersion(replaceTemplateId, versionId); setVersions(await listFormVersions(replaceTemplateId)); setPreview(null); setMessage('Versión restaurada. El ID del formulario y sus respuestas permanecen.'); }
    catch (error) { setMessage(error instanceof Error ? error.message : 'No se pudo restaurar.'); }
    finally { setImporting(false); }
  }

  async function submitDownloadMasterTemplate() {
    setDownloadingMaster(true);
    try {
      await downloadMasterTemplate(projectId);
      setMessage('Descarga de la plantilla maestra iniciada.');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible descargar la plantilla maestra.');
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
      setMessage('Descarga iniciada.');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible exportar la plantilla.');
    } finally {
      setExporting(false);
    }
  }

  return (
    <AppShell title="Importar / exportar XLSForm">
      <main className="audit-shell">
        {message ? <p role="status" className="erp-message">{message}</p> : null}

        <section className="audit-panel">
          <header>
            <div>
              <h2>Importar formulario (XLSForm, SurveyMonkey o LimeSurvey)</h2>
              <p>Sube un archivo .xlsx para crear una plantilla nueva del constructor. InfoMatt360 reconoce XLSForm con hojas "survey" y "choices", además de hojas estructuradas de otras fuentes.</p>
            </div>
          </header>
          <div className="ai-analyze-inline">
            <input ref={fileInputRef} type="file" accept=".xlsx" onChange={() => setPreview(null)} />
            <label>Destino
              <select value={replaceTemplateId} onChange={(event) => { setReplaceTemplateId(event.target.value); setPreview(null); }}>
                <option value="">Crear plantilla nueva</option>
                {templates.map((template) => <option key={template.id} value={template.id}>Reemplazar: {template.name} ({template.status})</option>)}
              </select>
            </label>
            <button disabled={importing} onClick={() => void submitPreview()}>Validar y comparar XLSForm</button>
            <button className="primary" disabled={importing || (replaceTemplateId !== '' && (!preview || !!preview.errors.length))} onClick={() => void submitImport()}>
              {importing ? 'Importando…' : replaceTemplateId ? 'Reemplazar en el mismo lugar' : 'Importar'}
            </button>
            <button disabled={downloadingMaster} onClick={() => void submitDownloadMasterTemplate()}>
              {downloadingMaster ? 'Generando…' : 'Descargar plantilla maestra'}
            </button>
          </div>
          {preview && <article className="ds-map-card"><h3>Comparación antes de aplicar</h3><p>{preview.added.length} nuevas · {preview.removed.length} eliminadas · {preview.modified.length} modificadas</p>{preview.added.length > 0 && <p><strong>Nuevas:</strong> {preview.added.join(', ')}</p>}{preview.removed.length > 0 && <p><strong>Se retiran de la versión activa:</strong> {preview.removed.join(', ')}</p>}{preview.modified.map((item) => <p key={item.name}><strong>{item.name}:</strong> {item.changes.join(', ')}</p>)}{preview.errors.map((error, index) => <p role="alert" key={index}>{error}</p>)}{preview.warnings.map((warning, index) => <p key={index}>{warning}</p>)}</article>}
          <small>La plantilla maestra trae un campo de ejemplo por cada tipo soportado (texto, numericos, seleccion, medios, GPS, repetibles, condicionales, validaciones, etc.) para usar como base y crear formularios rapidamente en Excel.</small>
          {replaceTemplateId ? (
            <small>Al reemplazar, el formulario conserva su enlace y sus registros. La estructura anterior queda guardada en el historial de versiones.</small>
          ) : null}
          {warnings.length ? (
            <article className="ds-map-card">
              <strong>Advertencias de la importación:</strong>
              <ul>
                {warnings.map((warning, index) => <li key={index}>{warning}</li>)}
              </ul>
            </article>
          ) : null}
          {replaceTemplateId && <article className="ds-map-card"><h3>Historial de versiones</h3>{versions.length ? versions.map((version) => <div key={version.id} className="forms-version-row"><span>v{version.version_number} · {version.question_count} preguntas · {new Date(version.created_at).toLocaleString('es-CO')}</span><button type="button" disabled={importing} onClick={() => void restore(version.id)}>Restaurar versión</button></div>) : <p>Aún no hay versiones anteriores.</p>}</article>}
        </section>

        <section className="audit-panel">
          <header>
            <div>
              <h2>Exportar a XLSForm</h2>
              <p>Descarga cualquier formulario del proyecto, diseñado a mano o importado, como archivo XLSForm .xlsx.</p>
            </div>
          </header>
          <div className="ai-analyze-inline">
            <label>Formulario
              <select value={exportTemplateId} onChange={(event) => setExportTemplateId(event.target.value)}>
                {templates.map((template) => <option key={template.id} value={template.id}>{template.name} ({template.status})</option>)}
              </select>
            </label>
            <button className="primary" disabled={exporting || !exportTemplateId} onClick={() => void submitExport()}>
              {exporting ? 'Generando…' : 'Descargar .xlsx'}
            </button>
          </div>
        </section>
      </main>
    </AppShell>
  );
}
