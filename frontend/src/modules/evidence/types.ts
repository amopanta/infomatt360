export type EvidenceAsset = {
  id: string;
  project_id: string;
  participant_id?: string | null;
  record_id?: string | null;
  asset_type: string;
  original_name: string;
  storage_provider: string;
  mime_type?: string | null;
  size_bytes: number;
  created_by?: string | null;
  created_at: string;
};

export type EvidenceUploader = { id: string; full_name: string };

export type EvidenceFilters = {
  participantId?: string;
  templateId?: string;
  status?: string;
  createdBy?: string;
  dateFrom?: string;
  dateTo?: string;
};
