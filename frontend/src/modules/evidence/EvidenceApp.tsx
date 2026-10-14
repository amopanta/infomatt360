import { useEffect, useState } from 'react';

import { AppShell } from '../../components/AppShell';
import { useI18n } from '../../i18n';
import { PROJECT_KEY } from '../auth/session';
import { fetchProjectParticipants } from '../participants/api';
import type { Participant } from '../participants/api';
import { fetchProjectTemplates } from '../records/api';
import type { TemplateSummary } from '../records/api';
import { downloadEvidenceAsset, downloadEvidenceBatch, fetchProjectEvidence, fetchProjectUploaders } from './api';
import type { EvidenceAsset, EvidenceFilters, EvidenceUploader } from './types';

const STATUS_KEYS: Record<string, string> = {
  draft: 'evidence.statusDraft', submitted: 'evidence.statusSubmitted', under_review: 'evidence.statusUnderReview',
  tech_approved: 'evidence.statusTechApproved', coordinator_approved: 'evidence.statusCoordinatorApproved',
  returned: 'evidence.statusReturned', corrected: 'evidence.statusCorrected', approved: 'evidence.statusApproved',
  rejected: 'evidence.statusRejected', cancelled: 'evidence.statusCancelled', archived: 'evidence.statusArchived',
};

const ASSET_TYPE_KEYS: Record<string, string> = {
  FILE: 'evidence.assetTypeFile', PDF: 'evidence.assetTypePdf', MULTIFILE: 'evidence.assetTypeMultifile',
  IMAGE: 'evidence.assetTypeImage', FINGERPRINT: 'evidence.assetTypeFingerprint',
  AUDIO: 'evidence.assetTypeAudio', VIDEO: 'evidence.assetTypeVideo', SIGNATURE: 'evidence.assetTypeSignature',
};

export function EvidenceApp() {
  const { t } = useI18n();
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';
  const [assets, setAssets] = useState<EvidenceAsset[]>([]);
  const [participants, setParticipants] = useState<Participant[]>([]);
  const [templates, setTemplates] = useState<TemplateSummary[]>([]);
  const [uploaders, setUploaders] = useState<EvidenceUploader[]>([]);
  const [filters, setFilters] = useState<EvidenceFilters>({});
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [message, setMessage] = useState(t('evidence.loading'));
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    if (!projectId) return;
    fetchProjectParticipants(projectId).then(setParticipants).catch(() => setParticipants([]));
    fetchProjectTemplates(projectId).then(setTemplates).catch(() => setTemplates([]));
    fetchProjectUploaders(projectId).then(setUploaders).catch(() => setUploaders([]));
  }, [projectId]);

  useEffect(() => {
    if (!projectId) return;
    setMessage(t('evidence.loading'));
    fetchProjectEvidence(projectId, filters)
      .then((rows) => {
        setAssets(rows);
        setSelected(new Set());
        setMessage(rows.length ? '' : t('evidence.noResults'));
      })
      .catch((error: Error) => setMessage(error.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, filters.participantId, filters.templateId, filters.status, filters.createdBy, filters.dateFrom, filters.dateTo, t]);

  const participantNames = new Map(participants.map((participant) => [participant.id, participant.full_name]));
  const uploaderNames = new Map(uploaders.map((uploader) => [uploader.id, uploader.full_name]));

  function updateFilter(patch: Partial<EvidenceFilters>) {
    setFilters((previous) => ({ ...previous, ...patch }));
  }

  function toggleSelection(assetId: string) {
    setSelected((previous) => {
      const next = new Set(previous);
      if (next.has(assetId)) next.delete(assetId);
      else next.add(assetId);
      return next;
    });
  }

  function toggleSelectAll() {
    setSelected((previous) => (previous.size === assets.length ? new Set() : new Set(assets.map((asset) => asset.id))));
  }

  async function handleDownloadBatch() {
    setDownloading(true);
    try {
      await downloadEvidenceBatch(projectId, selected.size ? { assetIds: Array.from(selected) } : filters);
    } catch (error) {
      setMessage((error as Error).message);
    } finally {
      setDownloading(false);
    }
  }

  return (
    <AppShell title={t('evidence.title')}>
      <main className="evidence-shell">
        <header className="evidence-header">
          <div>
            <h2>{t('evidence.title')}</h2>
            <p>{t('evidence.subtitle')}</p>
          </div>
          <button type="button" onClick={handleDownloadBatch} disabled={downloading || assets.length === 0}>
            {downloading ? t('evidence.generatingZip') : selected.size ? t('evidence.downloadZipSelected', { count: selected.size }) : t('evidence.downloadZipFilter')}
          </button>
        </header>

        <div className="evidence-filters">
          <select value={filters.participantId ?? ''} onChange={(event) => updateFilter({ participantId: event.target.value || undefined })}>
            <option value="">{t('evidence.allParticipants')}</option>
            {participants.map((participant) => (
              <option key={participant.id} value={participant.id}>{participant.full_name}</option>
            ))}
          </select>
          <select value={filters.templateId ?? ''} onChange={(event) => updateFilter({ templateId: event.target.value || undefined })}>
            <option value="">{t('evidence.allForms')}</option>
            {templates.map((template) => (
              <option key={template.id} value={template.id}>{template.name}</option>
            ))}
          </select>
          <select value={filters.status ?? ''} onChange={(event) => updateFilter({ status: event.target.value || undefined })}>
            <option value="">{t('evidence.allStatuses')}</option>
            {Object.entries(STATUS_KEYS).map(([value, key]) => (
              <option key={value} value={value}>{t(key)}</option>
            ))}
          </select>
          <select value={filters.createdBy ?? ''} onChange={(event) => updateFilter({ createdBy: event.target.value || undefined })}>
            <option value="">{t('evidence.allManagers')}</option>
            {uploaders.map((uploader) => (
              <option key={uploader.id} value={uploader.id}>{uploader.full_name}</option>
            ))}
          </select>
          <label>
            {t('evidence.dateFrom')}
            <input type="date" value={filters.dateFrom ?? ''} onChange={(event) => updateFilter({ dateFrom: event.target.value || undefined })} />
          </label>
          <label>
            {t('evidence.dateTo')}
            <input type="date" value={filters.dateTo ?? ''} onChange={(event) => updateFilter({ dateTo: event.target.value || undefined })} />
          </label>
        </div>

        {message ? <p role="status">{message}</p> : null}

        <div className="records-table-wrap">
          <table className="records-table">
            <thead>
              <tr>
                <th><input type="checkbox" aria-label={t('evidence.selectAllAriaLabel')} checked={assets.length > 0 && selected.size === assets.length} onChange={toggleSelectAll} /></th>
                <th>{t('evidence.columnFile')}</th>
                <th>{t('evidence.columnType')}</th>
                <th>{t('evidence.columnParticipant')}</th>
                <th>{t('evidence.columnManager')}</th>
                <th>{t('evidence.columnDate')}</th>
                <th>{t('evidence.columnDetail')}</th>
              </tr>
            </thead>
            <tbody>
              {assets.map((asset) => (
                <tr key={asset.id}>
                  <td><input type="checkbox" aria-label={t('evidence.selectItemAriaLabel', { name: asset.original_name })} checked={selected.has(asset.id)} onChange={() => toggleSelection(asset.id)} /></td>
                  <td>{asset.original_name}</td>
                  <td>{ASSET_TYPE_KEYS[asset.asset_type] ? t(ASSET_TYPE_KEYS[asset.asset_type]) : asset.asset_type}</td>
                  <td>{asset.participant_id ? participantNames.get(asset.participant_id) ?? '—' : '—'}</td>
                  <td>{asset.created_by ? uploaderNames.get(asset.created_by) ?? '—' : '—'}</td>
                  <td>{new Date(asset.created_at).toLocaleDateString()}</td>
                  <td><button type="button" onClick={() => downloadEvidenceAsset(asset.id, asset.original_name)}>{t('evidence.download')}</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </main>
    </AppShell>
  );
}
