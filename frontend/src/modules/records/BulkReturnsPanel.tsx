/** Devolución y reasignación masiva desde Excel (docs/141 §5): validar, revisar y confirmar. */
import { useState } from 'react';
import { useI18n } from '../../i18n';
import { bulkReturns, downloadBulkReturnTemplate, saveText, type BulkReturnResult } from './feedbackApi';

export function BulkReturnsPanel({ projectId }: { projectId: string }) {
  const { t } = useI18n();
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<BulkReturnResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');

  async function run(preview: boolean) {
    if (!file) return;
    setBusy(true); setMessage('');
    try {
      const response = await bulkReturns(projectId, file, preview);
      setResult(response);
      if (!preview) setMessage(t('feedback.bulkApplied', { count: response.aplicadas }));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('feedback.error'));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="participant-summary-card bulk-returns">
      <h3>{t('feedback.bulkTitle')}</h3>
      <p>{t('feedback.bulkDescription')}</p>
      <div className="participants-group-toolbar">
        <button type="button" onClick={() => void downloadBulkReturnTemplate().catch((e: Error) => setMessage(e.message))}>{t('feedback.bulkTemplate')}</button>
        <input type="file" accept=".xlsx,.csv" aria-label={t('feedback.bulkFile')} onChange={(e) => { setFile(e.target.files?.[0] ?? null); setResult(null); }} />
        <button type="button" disabled={!file || busy} onClick={() => void run(true)}>{t('feedback.bulkValidate')}</button>
      </div>
      {result && (
        <div role="status">
          <p>{t('feedback.bulkSummary', { rows: result.filas, records: result.registros_a_devolver, errors: result.errores, duplicates: result.duplicadas, already: result.ya_aplicadas })}</p>
          {result.vista_previa && result.registros_a_devolver > 0 && (
            <button type="button" disabled={busy} onClick={() => void run(false)}>{t('feedback.bulkConfirm', { count: result.registros_a_devolver })}</button>
          )}
          {result.errores_csv && <button type="button" onClick={() => saveText(result.errores_csv, 'errores_devoluciones.csv')}>{t('feedback.bulkErrors')}</button>}
          <div className="records-table-wrap">
            <table className="records-table">
              <thead><tr><th>{t('feedback.bulkRow')}</th><th>{t('feedback.bulkRecord')}</th><th>{t('feedback.bulkState')}</th><th>{t('feedback.bulkDetail')}</th></tr></thead>
              <tbody>
                {result.resultados.filter((r) => r.estado !== 'ok' && r.estado !== 'aplicada').slice(0, 200).map((r) => (
                  <tr key={r.fila}><td>{r.fila}</td><td>{r.id_registro}</td><td>{t(`feedback.bulkStates.${r.estado}`)}</td><td>{r.detalle}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
      {message && <p role="status">{message}</p>}
    </section>
  );
}
