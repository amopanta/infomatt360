import type { CatalogResult } from './catalogApi';

function number(value: number): string { return value.toLocaleString('es-CO', { maximumFractionDigits: 2 }); }

export function CatalogReportView({ report, publicView = false }: { report: CatalogResult; publicView?: boolean }) {
  function downloadCsv() {
    const rows = [['Indicador', 'Actual', 'Meta', 'Avance %', 'Municipio', 'Valor municipio']];
    report.indicators.forEach((item) => {
      if (item.municipalities.length) item.municipalities.forEach((place) => rows.push([item.title, String(item.actual), String(item.goal), String(item.progress_percent ?? ''), place.municipality, String(place.value)]));
      else rows.push([item.title, String(item.actual), String(item.goal), String(item.progress_percent ?? ''), '', '']);
    });
    const csv = '\uFEFF' + rows.map((row) => row.map((cell) => `"${cell.replace(/"/g, '""')}"`).join(',')).join('\r\n');
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `reporte-${report.name.replace(/[^a-z0-9]+/gi, '-')}.csv`;
    anchor.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  return <article className="catalog-result">
    <header><div><p>{publicView ? 'Reporte compartido · Solo lectura' : 'Reporte de indicadores'}</p><h1>{report.name}</h1>{report.description && <span>{report.description}</span>}</div><small>Actualizado: {new Date(report.generated_at).toLocaleString()}</small></header>
    <section className="catalog-indicator-grid">{report.indicators.map((item, index) => <div className="catalog-indicator" key={`${item.title}-${index}`}><h2>{item.title}</h2><div className="catalog-value"><strong>{number(item.actual)} {item.unit}</strong><span>Meta: {number(item.goal)} {item.unit}</span></div><div className="catalog-track"><span style={{ width: `${Math.min(item.progress_percent ?? 0, 100)}%`, background: (item.progress_percent ?? 0) >= 100 ? '#22a879' : (item.progress_percent ?? 0) >= 70 ? '#3489dc' : '#e6aa36' }} /></div><b>{item.progress_percent === null ? 'Sin meta definida' : `${number(item.progress_percent)}% de la meta`}</b>{item.municipalities.length > 0 && <div className="catalog-territory"><h3>Desglose por categoría</h3>{item.view_kind === 'bar' ? <div className="catalog-bars">{item.municipalities.map((place) => <div key={place.municipality}><span>{place.municipality}</span><div><i style={{ width: `${Math.max(2, place.value / Math.max(...item.municipalities.map((entry) => entry.value), 1) * 100)}%` }} /></div><strong>{number(place.value)}</strong></div>)}</div> : <table><thead><tr><th>Categoría</th><th>Resultado</th></tr></thead><tbody>{item.municipalities.map((place) => <tr key={place.municipality}><td>{place.municipality}</td><td>{number(place.value)} {item.unit}</td></tr>)}</tbody></table>}</div>}</div>)}</section>
    <footer><button type="button" onClick={downloadCsv}>Descargar CSV</button><button type="button" onClick={() => window.print()}>PDF / Imprimir</button></footer>
  </article>;
}
