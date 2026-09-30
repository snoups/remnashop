import { apiDelete, apiGet, apiPost, apiPut, BASE_URL } from "@shared/api/http";
import { getAccessToken } from "@shared/lib/token-storage";

export type BackupKind = "DATABASE" | "ASSETS";
export type BackupRunStatus = "PENDING" | "RUNNING" | "COMPLETED" | "FAILED";

export interface BackupSettings {
  enabled: boolean;
  interval_hours: number;
  max_files: number;
}

export function getBackupSettings(signal?: AbortSignal): Promise<BackupSettings> {
  return apiGet<BackupSettings>("/backups/settings", signal);
}

export interface UpdateBackupSettingsRequest {
  enabled?: boolean;
  interval_hours?: number;
  max_files?: number;
}

export function updateBackupSettings(payload: UpdateBackupSettingsRequest): Promise<BackupSettings> {
  return apiPut<BackupSettings, UpdateBackupSettingsRequest>("/backups/settings", payload);
}

// Drops the stored row, so every field reads back as its default.
export function resetBackupSettings(): Promise<BackupSettings> {
  return apiDelete<BackupSettings>("/backups/settings");
}

export interface BackupRun {
  id: number;
  kind: BackupKind;
  status: BackupRunStatus;
  size_bytes: number | null;
  checksum_sha256: string | null;
  triggered_by: number | null;
  error: string | null;
  created_at: string;
  finished_at: string | null;
}

export const DEFAULT_PAGE_SIZE = 50;

export interface BackupRunListPage {
  items: BackupRun[];
  total: number;
}

export interface BackupRunListFilters {
  kind?: BackupKind;
  status?: BackupRunStatus;
  page?: number;
  pageSize?: number;
}

export function listBackupRuns(
  filters: BackupRunListFilters = {},
  signal?: AbortSignal,
): Promise<BackupRunListPage> {
  const params = new URLSearchParams();
  if (filters.kind) params.set("kind", filters.kind);
  if (filters.status) params.set("status", filters.status);
  params.set("page", String(filters.page ?? 1));
  params.set("page_size", String(filters.pageSize ?? DEFAULT_PAGE_SIZE));

  return apiGet<BackupRunListPage>(`/backups/runs?${params.toString()}`, signal);
}

export interface BackupStats {
  completed_count: number;
  failed_count: number;
  total_size_bytes: number;
  last_database_backup: BackupRun | null;
  next_run_at: string | null;
}

export function getBackupStats(signal?: AbortSignal): Promise<BackupStats> {
  return apiGet<BackupStats>("/backups/stats", signal);
}

export function createBackupRun(kind: BackupKind): Promise<BackupRun> {
  return apiPost<BackupRun, { kind: BackupKind }>("/backups/runs", { kind });
}

export function deleteBackupRun(runId: number): Promise<void> {
  return apiDelete<void>(`/backups/runs/${runId}`);
}

// Not routed through apiGet: the response is a raw file, not JSON -- apiGet
// always calls response.json(). Mirrors entities/banners/api.ts's
// fetchBannerImageBlob for the same reason.
export async function fetchBackupRunFile(runId: number): Promise<{ blob: Blob; filename: string }> {
  const token = getAccessToken();
  const response = await fetch(`${BASE_URL}/backups/runs/${runId}/download`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!response.ok) {
    throw new Error(`Failed to download backup: ${response.status}`);
  }
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const match = /filename="?([^"]+)"?/.exec(disposition);
  const filename = match ? match[1] : `backup-${runId}`;
  return { blob: await response.blob(), filename };
}
