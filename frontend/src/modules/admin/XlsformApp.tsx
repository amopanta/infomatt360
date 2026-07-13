import { useEffect, useRef, useState } from 'react';

import { AppShell } from '../../components/AppShell';
import { PROJECT_KEY } from '../auth/session';
import { fetchProjectTemplates } from '../records/api';
import type { TemplateSummary } from '../records/api';
import { downloadMasterTemplate, exportXlsform, importXlsform } from './xlsformApi';

export function XlsformApp() {
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';
  const [templates, setTemplates] = useState<TemplateSummary[]>([]);
  const [exportTemplateId, setExportTemplateId] = useState('');
  const [message, setMessage] = useState('');
  const [importing, setImporting] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [downloadingMaster, setDownloadingMaster] = useState(false);
  const [warnings, setWarnings] = useState<string[]>([]);
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

  async function submitImport() {
    const file = fileInputRef.current?.files?.[0];
    if (!file) {
      setMessage('Selecciona un archivo .xlsx antes de importar.');
      return;
    }
    setImporting(true);
    setWarnings([]);
    try {
      const result = await importXlsform(projectId, file);
      setMessage(`Plantilla importada (${result.imported_fields} campo(s)).`);
      setWarnings(result.warnings);
      if (fileInputRef.current) fileInputRef.current.value = '';
      await loadTemplates();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible importar el archivo XLSForm.');
    } finally {
      setImporting(false);
    }
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
              <p>Sube un archivo .xlsx para crear una plantilla nueva del constructor. Detecta automaticamente el formato: XLSForm/ODK/KoboToolbox (hojas "survey"/"choices"), o el formato SurveyMonkey/LimeSurvey de la plantilla de referencia (ver docs/81, docs/93 y docs/94).</p>
            </div>
          </header>
          <div className="ai-analyze-inline">
            <input ref={fileInputRef} type="file" accept=".xlsx" />
            <button className="primary" disabled={importing} onClick={() => void submitImport()}>
              {importing ? 'Importando…' : 'Importar'}
            </button>
            <button disabled={downloadingMaster} onClick={() => void submitDownloadMasterTemplate()}>
              {downloadingMaster ? 'Generando…' : 'Descargar plantilla maestra'}
            </button>
          </div>
          <small>La plantilla maestra trae un campo de ejemplo por cada tipo soportado (texto, numericos, seleccion, medios, GPS, repetibles, condicionales, validaciones, etc.) para usar como base y crear formularios rapidamente en Excel.</small>
          {warnings.length ? (
            <article className="ds-map-card">
              <strong>Advertencias de la importación:</strong>
              <ul>
                {warnings.map((warning, index) => <li key={index}>{warning}</li>)}
              </ul>
            </article>
          ) : null}
        </section>

        <section className="audit-panel">
          <header>
            <div>
              <h2>Exportar a XLSForm</h2>
              <p>Descarga cualquier formulario del proyecto (diseñado a mano o importado) como un archivo .xlsx compatible con KoboToolbox/ODK (ver docs/93).</p>
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
