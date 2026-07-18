import { useEffect, useState } from 'react';

import { AppShell } from '../../components/AppShell';
import { PROJECT_KEY } from '../auth/session';
import { fetchProjectParticipants } from '../participants/api';
import type { Participant } from '../participants/api';
import { fetchProjectTemplates } from '../records/api';
import type { TemplateSummary } from '../records/api';
import { downloadEvidenceAsset, downloadEvidenceBatch, fetchProjectEvidence, fetchProjectUploaders } from './api';
import type { EvidenceAsset, EvidenceFilters, EvidenceUploader } from './types';

const STATUS_LABELS: Record<string, string> = {
  draft: 'Borrador', submitted: 'Enviado', under_review: 'En revisión',
  tech_approved: 'Aprobado técnico', coordinator_approved: 'Aprobado coordinación',
  returned: 'Devuelto', corrected: 'Corregido', approved: 'Aprobado',
  rejected: 'Rechazado', cancelled: 'Cancelado', archived: 'Archivado',
};

const ASSET_TYPE_LABELS: Record<string, string> = {
  FILE: 'Archivo', PDF: 'PDF', MULTIFILE: 'Múltiples archivos', IMAGE: 'Imagen',
  AUDIO: 'Audio', VIDEO: 'Video', SIGNATURE: 'Firma',
};

export function EvidenceApp() {
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';
  const [assets, setAssets] = useState<EvidenceAsset[]>([]);
  const [participants, setParticipants] = useState<Participant[]>([]);
  const [templates, setTemplates] = useState<TemplateSummary[]>([]);
  const [uploaders, setUploaders] = useState<EvidenceUploader[]>([]);
  const [filters, setFilters] = useState<EvidenceFilters>({});
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [message, setMessage] = useState('Cargando evidencias...');
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    if (!projectId) return;
    fetchProjectParticipants(projectId).then(setParticipants).catch(() => setParticipants([]));
    fetchProjectTemplates(projectId).then(setTemplates).catch(() => setTemplates([]));
    fetchProjectUploaders(projectId).then(setUploaders).catch(() => setUploaders([]));
  }, [projectId]);

  useEffect(() => {
    if (!projectId) return;
    setMessage('Cargando evidencias...');
    fetchProjectEvidence(projectId, filters)
      .then((rows) => {
        setAssets(rows);
        setSelected(new Set());
        setMessage(rows.length ? '' : 'No hay evidencias que coincidan con los filtros.');
      })
      .catch((error: Error) => setMessage(error.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, filters.participantId, filters.templateId, filters.status, filters.createdBy, filters.dateFrom, filters.dateTo]);

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
    <AppShell title="Evidencias">
      <main className="evidence-shell">
        <header className="evidence-header">
          <div>
            <h2>Evidencias</h2>
            <p>Filtra y descarga en lote las evidencias capturadas en el proyecto, con renombrado automático.</p>
          </div>
          <button type="button" onClick={handleDownloadBatch} disabled={downloading || assets.length === 0}>
            {downloading ? 'Generando ZIP...' : selected.size ? `Descargar ZIP (${selected.size} seleccionadas)` : 'Descargar ZIP (filtro actual)'}
          </button>
        </header>

        <div className="evidence-filters">
          <select value={filters.participantId ?? ''} onChange={(event) => updateFilter({ participantId: event.target.value || undefined })}>
            <option value="">Todos los participantes</option>
            {participants.map((participant) => (
              <option key={participant.id} value={participant.id}>{participant.full_name}</option>
            ))}
          </select>
          <select value={filters.templateId ?? ''} onChange={(event) => updateFilter({ templateId: event.target.value || undefined })}>
            <option value="">Todos los formularios</option>
            {templates.map((template) => (
              <option key={template.id} value={template.id}>{template.name}</option>
            ))}
          </select>
          <select value={filters.status ?? ''} onChange={(event) => updateFilter({ status: event.target.value || undefined })}>
            <option value="">Todos los estados</option>
            {Object.entries(STATUS_LABELS).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
          <select value={filters.createdBy ?? ''} onChange={(event) => updateFilter({ createdBy: event.target.value || undefined })}>
            <option value="">Todos los gestores</option>
            {uploaders.map((uploader) => (
              <option key={uploader.id} value={uploader.id}>{uploader.full_name}</option>
            ))}
          </select>
          <label>
            Desde
            <input type="date" value={filters.dateFrom ?? ''} onChange={(event) => updateFilter({ dateFrom: event.target.value || undefined })} />
          </label>
          <label>
            Hasta
            <input type="date" value={filters.dateTo ?? ''} onChange={(event) => updateFilter({ dateTo: event.target.value || undefined })} />
          </label>
        </div>

        {message ? <p role="status">{message}</p> : null}

        <div className="records-table-wrap">
          <table className="records-table">
            <thead>
              <tr>
                <th><input type="checkbox" aria-label="Seleccionar todas las evidencias listadas" checked={assets.length > 0 && selected.size === assets.length} onChange={toggleSelectAll} /></th>
                <th>Archivo</th>
                <th>Tipo</th>
                <th>Participante</th>
                <th>Gestor</th>
                <th>Fecha</th>
                <th>Detalle</th>
              </tr>
            </thead>
            <tbody>
              {assets.map((asset) => (
                <tr key={asset.id}>
                  <td><input type="checkbox" aria-label={`Seleccionar evidencia ${asset.original_name}`} checked={selected.has(asset.id)} onChange={() => toggleSelection(asset.id)} /></td>
                  <td>{asset.original_name}</td>
                  <td>{ASSET_TYPE_LABELS[asset.asset_type] ?? asset.asset_type}</td>
                  <td>{asset.participant_id ? participantNames.get(asset.participant_id) ?? '—' : '—'}</td>
                  <td>{asset.created_by ? uploaderNames.get(asset.created_by) ?? '—' : '—'}</td>
                  <td>{new Date(asset.created_at).toLocaleDateString()}</td>
                  <td><button type="button" onClick={() => downloadEvidenceAsset(asset.id, asset.original_name)}>Descargar</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </main>
    </AppShell>
  );
}
