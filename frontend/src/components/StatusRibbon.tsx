import { useI18n } from '../i18n';

type Translate = (key: string, params?: Record<string, string | number>) => string;

// Orden del recorrido de un registro: de la captura a la decision final. La
// cinta de estados los dibuja en este orden (docs/150).
const STATUS_ORDER = ['draft', 'submitted', 'under_review', 'returned', 'corrected', 'tech_approved', 'coordinator_approved', 'approved', 'rejected', 'cancelled', 'archived'];

/** Cinta proporcional con el recorrido de los registros del proyecto: cuanto
 * esta en borrador, enviado, en revision, devuelto o aprobado. Es lo primero
 * que necesita ver un coordinador al entrar. Se usa en Inicio y en Reportes. */
export function StatusRibbon({ total, byStatus }: { total: number; byStatus: Record<string, number> }) {
  const { t } = useI18n();
  const statuses = Object.entries(byStatus)
    .filter(([, count]) => count > 0)
    .sort(([a], [b]) => rank(a) - rank(b));
  return (
    <section className="home-ribbon" aria-labelledby="home-ribbon-title">
      <h2 id="home-ribbon-title"><span>{total.toLocaleString()}</span> {t('dashboard.records').toLowerCase()}<small>{t('dashboard.pipelineTitle')}</small></h2>
      {total ? (
        <>
          <div className="home-ribbon-bar" aria-hidden="true">
            {statuses.map(([status, count]) => <span key={status} className={`status-${status}`} style={{ flexGrow: count }} />)}
          </div>
          <ul>
            {statuses.map(([status, count]) => (
              <li key={status} className={`status-${status}`}>
                <a href="/records"><strong>{count.toLocaleString()}</strong>{statusLabel(t, status)}</a>
              </li>
            ))}
          </ul>
        </>
      ) : <p>{t('dashboard.pipelineEmpty')}</p>}
    </section>
  );
}

function rank(status: string): number {
  const index = STATUS_ORDER.indexOf(status);
  return index < 0 ? STATUS_ORDER.length : index;
}

export function statusLabel(t: Translate, status: string): string {
  const key = `participants.statusLabels.${status}`;
  const label = t(key);
  return label === key ? status : label;
}

