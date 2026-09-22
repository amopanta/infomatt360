import { useEffect, useState } from 'react';
import { CatalogReportView } from './CatalogReportView';
import { CommitteeReportView } from './CommitteeReportView';
import { getSharedReport } from './catalogApi';
import type { CatalogResult } from './catalogApi';

export function PublicReportApp() {
  const token = window.location.pathname.split('/')[2] ?? '';
  const [report, setReport] = useState<CatalogResult | null>(null);
  const [message, setMessage] = useState('Cargando reporte…');
  useEffect(() => { getSharedReport(token).then((data) => { setReport(data); setMessage(''); }).catch((error: Error) => setMessage(error.message)); }, [token]);
  return <main className="public-report-page"><div className="public-report-brand">▦ InfoMatt360 · Reportes</div>{message && <p role="status" className="public-report-message">{message}</p>}{report && (report.report_kind === 'committee' ? <CommitteeReportView report={report} publicView /> : <CatalogReportView report={report} publicView />)}</main>;
}
