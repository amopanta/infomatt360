import { useEffect, useState } from 'react';

import { AppShell } from '../../components/AppShell';
import { useI18n } from '../../i18n';
import { PROJECT_KEY } from '../auth/session';
import { downloadProjectFormReport, fetchProjectFormReport, type ParticipantFormReportRow } from './api';

function formatApplicationDate(value: string | null): string {
  if (!value) return '—';
  const iso = /(?:Z|[+-]\d\d:\d\d)$/.test(value) ? value : `${value}Z`;
  return new Date(iso).toLocaleString();
}

export function AppliedActivitiesApp() {
  const { t } = useI18n();
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';
  const [rows, setRows] = useState<ParticipantFormReportRow[]>([]);
  const [query, setQuery] = useState('');
  const [group, setGroup] = useState('');
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState('');
  const labels: Record<string, string> = {
    assigned: t('participants.assignmentAssigned'),
    in_progress: t('participants.assignmentInProgress'),
    completed: t('participants.assignmentCompleted'),
    closed: t('participants.assignmentClosed'),
  };

  useEffect(() => {
    setRows([]);
    setLoading(true);
    setMessage('');
    if (!projectId) {
      setMessage(t('participants.selectProjectForReport'));
      setLoading(false);
      return;
    }
    void fetchProjectFormReport(projectId)
      .then(setRows)
      .catch((error: Error) => setMessage(error.message))
      .finally(() => setLoading(false));
  }, [projectId]);

  const groups = Array.from(new Set(rows.map((row) => row.group_name).filter((name): name is string => Boolean(name)))).sort();
  const needle = query.trim().toLocaleLowerCase();
  const visible = rows.filter((row) => (!group || row.group_name === group) && (!needle ||
    [row.participant_name, row.document_id, row.external_code, row.department, row.municipality, row.template_name]
      .some((value) => (value || '').toLocaleLowerCase().includes(needle))));

  async function exportExcel() {
    try {
      await downloadProjectFormReport(projectId, query, group);
      setMessage('');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('participants.exportError'));
    }
  }

  return <AppShell title={t('participants.appliedActivitiesTitle')}>
    <main className="participants-shell applied-activities-shell">
      <header className="participants-header">
        <div><h2>{t('participants.appliedActivitiesTitle')}</h2><p>{t('participants.appliedActivitiesDescription')}</p></div>
      </header>
      <div className="participants-group-toolbar">
        <input type="search" aria-label={t('participants.searchActivities')} placeholder={t('participants.searchActivities')} value={query} onChange={(event) => setQuery(event.target.value)} />
        <label>{t('participants.groupLabel')}<select value={group} onChange={(event) => setGroup(event.target.value)}><option value="">{t('participants.allGroups')}</option>{groups.map((name) => <option key={name} value={name}>{name}</option>)}</select></label>
        <button type="button" disabled={!projectId || loading} onClick={() => void exportExcel()}>{t('participants.exportExcel')}</button>
        <span>{t('participants.activityCount', { count: visible.length })}</span>
      </div>
      {loading && <p role="status">{t('participants.loadingActivities')}</p>}
      {message && <p role="status">{message}</p>}
      {!loading && !message && !visible.length && <p>{t('participants.noActivities')}</p>}
      {!loading && visible.length > 0 && <div className="records-table-wrap">
        <table className="records-table applied-activities-table">
          <thead><tr>
            <th>{t('participants.name')}</th><th>{t('participants.document')}</th><th>{t('participants.group')}</th>
            <th>{t('participants.municipality')}</th><th>{t('participants.assignedForms')}</th>
            <th>{t('participants.status')}</th><th>{t('participants.applicationDate')}</th><th>{t('participants.detail')}</th>
          </tr></thead>
          <tbody>{visible.map((row) => <tr key={`${row.participant_id}:${row.template_id}`}>
            <td data-label={t('participants.name')}>{row.participant_name}</td>
            <td data-label={t('participants.document')}>{row.document_id || '—'}</td>
            <td data-label={t('participants.group')}>{row.group_name || '—'}</td>
            <td data-label={t('participants.municipality')}>{row.municipality || '—'}</td>
            <td data-label={t('participants.assignedForms')}>{row.template_name}</td>
            <td data-label={t('participants.status')}>{row.applied_at ? t('participants.applied') : labels[row.assignment_status] || row.assignment_status}</td>
            <td data-label={t('participants.applicationDate')}>{formatApplicationDate(row.applied_at)}</td>
            <td data-label={t('participants.detail')}><a href={`/participants/${row.participant_id}`}>{t('participants.viewHistory')}</a></td>
          </tr>)}</tbody>
        </table>
      </div>}
    </main>
  </AppShell>;
}
