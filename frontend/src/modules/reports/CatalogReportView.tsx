import { useI18n } from '../../i18n';
import type { CatalogResult } from './catalogApi';

function number(value: number): string { return value.toLocaleString('es-CO', { maximumFractionDigits: 2 }); }

export function CatalogReportView({ report, publicView = false }: { report: CatalogResult; publicView?: boolean }) {
  const { t } = useI18n();

  function downloadCsv() {
    const rows = [[t('reports.catalogView.csvCode'), t('reports.catalogView.csvIndicator'), t('reports.catalogView.csvActual'), t('reports.catalogView.csvGoal'), t('reports.catalogView.csvProgress'), t('reports.catalogView.csvMunicipality'), t('reports.catalogView.csvMunicipalityValue')]];
    report.indicators.forEach((item) => {
      if (item.municipalities.length) item.municipalities.forEach((place) => rows.push([item.code, item.title, String(item.actual), String(item.goal), String(item.progress_percent ?? ''), place.municipality, String(place.value)]));
      else rows.push([item.code, item.title, String(item.actual), String(item.goal), String(item.progress_percent ?? ''), '', '']);
    });
    const csv = '﻿' + rows.map((row) => row.map((cell) => `"${cell.replace(/"/g, '""')}"`).join(',')).join('\r\n');
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `reporte-${report.name.replace(/[^a-z0-9]+/gi, '-')}.csv`;
    anchor.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  return <article className="catalog-result">
    <header><div><p>{publicView ? t('reports.catalogView.sharedReadOnly') : t('reports.catalogView.indicatorReport')}</p><h1>{report.name}</h1>{report.description && <span>{report.description}</span>}</div><small>{t('reports.catalogView.updatedAt', { date: new Date(report.generated_at).toLocaleString() })}</small></header>
    <section className="catalog-indicator-grid">{report.indicators.map((item, index) => <div className="catalog-indicator" key={`${item.title}-${index}`}><h2>{item.code ? `${item.code} · ` : ''}{item.title}</h2><div className="catalog-value"><strong>{number(item.actual)} {item.unit}</strong><span>{t('reports.catalogView.goalValue', { value: number(item.goal), unit: item.unit })}</span></div><div className="catalog-track"><span style={{ width: `${Math.min(item.progress_percent ?? 0, 100)}%`, background: (item.progress_percent ?? 0) >= 100 ? '#22a879' : (item.progress_percent ?? 0) >= 70 ? '#3489dc' : '#e6aa36' }} /></div><b>{item.progress_percent === null ? t('reports.catalogView.noGoal') : t('reports.catalogView.progressPercent', { percent: number(item.progress_percent) })}</b>{item.municipalities.length > 0 && <div className="catalog-territory"><h3>{t('reports.catalogView.categoryBreakdown')}</h3>{item.view_kind === 'bar' ? <div className="catalog-bars">{item.municipalities.map((place) => <div key={place.municipality}><span>{place.municipality}</span><div><i style={{ width: `${Math.max(2, place.value / Math.max(...item.municipalities.map((entry) => entry.value), 1) * 100)}%` }} /></div><strong>{number(place.value)}</strong></div>)}</div> : <table><thead><tr><th>{t('reports.catalogView.categoryHeader')}</th><th>{t('reports.catalogView.resultHeader')}</th></tr></thead><tbody>{item.municipalities.map((place) => <tr key={place.municipality}><td>{place.municipality}</td><td>{number(place.value)} {item.unit}</td></tr>)}</tbody></table>}</div>}</div>)}</section>
    <footer><button type="button" onClick={downloadCsv}>{t('reports.catalogView.downloadCsv')}</button><button type="button" onClick={() => window.print()}>{t('reports.catalogView.printPdf')}</button></footer>
  </article>;
}
