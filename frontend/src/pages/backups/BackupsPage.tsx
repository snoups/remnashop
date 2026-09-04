import {
  AlertCircle,
  ChevronDown,
  Database,
  Download,
  Filter,
  HardDrive,
  Inbox,
  Loader2,
  Play,
  Trash2,
} from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import {
  type BackupKind,
  type BackupRun,
  createBackupRun,
  DEFAULT_PAGE_SIZE,
  deleteBackupRun,
  fetchBackupRunFile,
  getBackupSettings,
  listBackupRuns,
  updateBackupSettings,
} from "@entities/backups/api";
import { useCurrentUser } from "@entities/user/use-current-user";
import { getErrorMessage } from "@shared/api/http";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { parseRequiredInt } from "@shared/lib/number-input";
import { toast } from "@shared/lib/toast";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { SelectDropdown } from "@shared/ui/SelectDropdown";
import { Switch } from "@shared/ui/Switch";

type SettingsState = { kind: "loading" } | { kind: "error" } | { kind: "ready" };
type RunsState =
  | { kind: "loading" }
  | { kind: "error" }
  | { kind: "ready"; items: BackupRun[]; total: number };

const BACKUP_KINDS: BackupKind[] = ["DATABASE", "ASSETS"];

const fieldClassName =
  "rounded-xl border border-border bg-input/60 px-3 py-2 text-sm text-foreground outline-none focus:border-primary";

function formatBytes(bytes: number | null): string {
  if (bytes === null) return "—";
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let value = bytes / 1024;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex++;
  }
  return `${value.toFixed(1)} ${units[unitIndex]}`;
}

const STATUS_BADGE_CLASSNAME: Record<BackupRun["status"], string> = {
  COMPLETED: "border-success/30 bg-success/10 text-success",
  RUNNING: "border-warning/30 bg-warning/10 text-warning",
  PENDING: "border-border bg-white/[0.04] text-muted-foreground",
  FAILED: "border-error/30 bg-error/10 text-error",
};

export function BackupsPage() {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();

  const [settingsState, setSettingsState] = useState<SettingsState>({ kind: "loading" });
  const [isSavingSettings, setIsSavingSettings] = useState(false);
  const [enabled, setEnabled] = useState(false);
  const [intervalHours, setIntervalHours] = useState("24");
  const [maxFiles, setMaxFiles] = useState("14");
  const [runKind, setRunKind] = useState<BackupKind>("DATABASE");
  const [isStartingRun, setIsStartingRun] = useState(false);

  const [runsState, setRunsState] = useState<RunsState>({ kind: "loading" });
  const [page, setPage] = useState(1);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [downloadingId, setDownloadingId] = useState<number | null>(null);
  const [pendingDelete, setPendingDelete] = useState<BackupRun | null>(null);

  const currentUserState = useCurrentUser();
  const permissions =
    currentUserState.kind === "ready" ? currentUserState.data.effective_permissions : [];
  const canManageSettings = permissions.includes("BACKUPS_SETTINGS_MANAGE");
  const canCreateRun = permissions.includes("BACKUPS_RUN_CREATE");
  const canDownload = permissions.includes("BACKUPS_RUN_DOWNLOAD");
  const canDeleteRun = permissions.includes("BACKUPS_RUN_DELETE");
  const canViewRuns = permissions.includes("BACKUPS_RUN_VIEW");

  const loadRuns = (signal?: AbortSignal) => {
    setPage(1);
    listBackupRuns({ page: 1, pageSize: DEFAULT_PAGE_SIZE }, signal)
      .then((result) => {
        if (!signal?.aborted) setRunsState({ kind: "ready", items: result.items, total: result.total });
      })
      .catch(() => {
        if (!signal?.aborted) setRunsState({ kind: "error" });
      });
  };

  useEffect(() => {
    const controller = new AbortController();
    getBackupSettings(controller.signal)
      .then((settings) => {
        if (controller.signal.aborted) return;
        setEnabled(settings.enabled);
        setIntervalHours(String(settings.interval_hours));
        setMaxFiles(String(settings.max_files));
        setSettingsState({ kind: "ready" });
      })
      .catch(() => {
        if (!controller.signal.aborted) setSettingsState({ kind: "error" });
      });

    if (canViewRuns) loadRuns(controller.signal);
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSaveSettings = async (event: FormEvent) => {
    event.preventDefault();

    const parsedIntervalHours = parseRequiredInt(intervalHours, 1);
    const parsedMaxFiles = parseRequiredInt(maxFiles, 1);
    if (parsedIntervalHours === undefined || parsedMaxFiles === undefined) {
      toast.error(t("errors.invalidNumber"));
      return;
    }

    setIsSavingSettings(true);
    try {
      const settings = await updateBackupSettings({
        enabled,
        interval_hours: parsedIntervalHours,
        max_files: parsedMaxFiles,
      });
      setEnabled(settings.enabled);
      setIntervalHours(String(settings.interval_hours));
      setMaxFiles(String(settings.max_files));
      toast.success(t("backups.settings.saved"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("backups.settings.error")));
    } finally {
      setIsSavingSettings(false);
    }
  };

  const handleRunNow = async () => {
    setIsStartingRun(true);
    try {
      const run = await createBackupRun(runKind);
      toast.success(t("backups.settings.runStarted"));
      if (runsState.kind === "ready") {
        setRunsState({ kind: "ready", items: [run, ...runsState.items], total: runsState.total + 1 });
      }
    } catch (err) {
      toast.error(getErrorMessage(err, t("backups.settings.runError")));
    } finally {
      setIsStartingRun(false);
    }
  };

  // Offset pagination + local optimistic edits (run-now prepends, delete
  // removes) can drift a row at a page boundary; acceptable here.
  // offset drift on boundary, switch to keyset if it bites.
  const handleLoadMore = async () => {
    const nextPage = page + 1;
    setIsLoadingMore(true);
    try {
      const result = await listBackupRuns({ page: nextPage, pageSize: DEFAULT_PAGE_SIZE });
      setRunsState((prev) =>
        prev.kind === "ready"
          ? { kind: "ready", items: [...prev.items, ...result.items], total: result.total }
          : prev,
      );
      setPage(nextPage);
    } catch {
      // keep current items on failure; the load-more button stays available to retry
    } finally {
      setIsLoadingMore(false);
    }
  };

  const handleDownload = async (run: BackupRun) => {
    setDownloadingId(run.id);
    try {
      const { blob, filename } = await fetchBackupRunFile(run.id);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch {
      toast.error(t("backups.runs.downloadError"));
    } finally {
      setDownloadingId(null);
    }
  };

  const handleDelete = async (run: BackupRun) => {
    try {
      await deleteBackupRun(run.id);
      if (runsState.kind === "ready") {
        setRunsState({
          kind: "ready",
          items: runsState.items.filter((item) => item.id !== run.id),
          total: runsState.total - 1,
        });
      }
    } catch (err) {
      toast.error(getErrorMessage(err, t("backups.runs.deleteError")));
    }
  };

  const hasMore = runsState.kind === "ready" && runsState.items.length < runsState.total;

  return (
    <div className="flex flex-col gap-4">
      <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-4">
        {settingsState.kind === "loading" && (
          <div className="flex justify-center py-6 text-muted-foreground">
            <Loader2 className="size-5 animate-spin" />
          </div>
        )}
        {settingsState.kind === "error" && (
          <div className="flex flex-col items-center gap-2 py-6 text-error">
            <AlertCircle className="size-5" />
            <p className="text-sm">{t("backups.loadError")}</p>
          </div>
        )}
        {settingsState.kind === "ready" && (
          <form onSubmit={(event) => void handleSaveSettings(event)} className="flex flex-wrap items-end gap-3">
            <div className="flex min-w-40 flex-col gap-1.5">
              <span className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                {t("backups.settings.enabledLabel")}
              </span>
              <div className="flex h-[38px] items-center">
                <Switch checked={enabled} onChange={setEnabled} ariaLabel={t("backups.settings.enabledLabel")} />
              </div>
            </div>
            <div className="flex min-w-32 flex-col gap-1.5">
              <label htmlFor="backups-interval" className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                {t("backups.settings.intervalLabel")}
              </label>
              <input
                id="backups-interval"
                type="number"
                min={1}
                step="1"
                value={intervalHours}
                onChange={(event) => setIntervalHours(event.target.value)}
                className={fieldClassName}
              />
            </div>
            <div className="flex min-w-32 flex-col gap-1.5">
              <label htmlFor="backups-max-files" className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                {t("backups.settings.maxFilesLabel")}
              </label>
              <input
                id="backups-max-files"
                type="number"
                min={1}
                step="1"
                value={maxFiles}
                onChange={(event) => setMaxFiles(event.target.value)}
                className={fieldClassName}
              />
            </div>
            {canManageSettings && (
              <motion.button
                type="submit"
                disabled={isSavingSettings}
                {...bounceTap(bounceStrength)}
                className="rounded-full border border-border px-4 py-2 text-sm font-medium text-foreground/90 transition-colors hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {isSavingSettings ? t("backups.settings.saving") : t("backups.settings.save")}
              </motion.button>
            )}

            {canCreateRun && (
              <div className="ml-auto flex items-end gap-2">
                <div className="flex min-w-36 flex-col gap-1.5">
                  <span className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                    {t("backups.settings.runKindLabel")}
                  </span>
                  <SelectDropdown
                    id="backups-run-kind"
                    value={runKind}
                    onChange={(value) => setRunKind(value as BackupKind)}
                    icon={Filter}
                    placeholder={t(`backups.kind.${runKind}`)}
                    options={BACKUP_KINDS.map((value) => ({ value, label: t(`backups.kind.${value}`) }))}
                  />
                </div>
                <motion.button
                  type="button"
                  onClick={() => void handleRunNow()}
                  disabled={isStartingRun}
                  {...bounceTap(bounceStrength)}
                  className="flex items-center gap-1.5 rounded-full bg-accent px-4 py-2 text-[13px] font-semibold text-primary transition-colors hover:bg-primary/20 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {isStartingRun ? <Loader2 className="size-3.5 animate-spin" /> : <Play className="size-3.5" />}
                  {t("backups.settings.runNow")}
                </motion.button>
              </div>
            )}
          </form>
        )}
      </div>

      {canViewRuns && (
        <div className="relative rounded-2xl border border-white/[0.08] bg-white/[0.03] p-4">
          {runsState.kind === "loading" && (
            <div className="flex flex-col items-center gap-2 py-12 text-muted-foreground">
              <Loader2 className="size-5 animate-spin" />
              <p className="text-sm">{t("backups.loading")}</p>
            </div>
          )}
          {runsState.kind === "error" && (
            <div className="flex flex-col items-center gap-2 py-12 text-error">
              <AlertCircle className="size-5" />
              <p className="text-sm">{t("backups.loadError")}</p>
            </div>
          )}
          {runsState.kind === "ready" && (
            <>
              {runsState.items.length === 0 && (
                <div className="flex flex-col items-center gap-2 py-12 text-muted-foreground">
                  <Inbox className="size-5" />
                  <p className="text-sm">{t("backups.empty")}</p>
                </div>
              )}
              {runsState.items.length > 0 && (
                <>
                  <div className="flex flex-col divide-y divide-border/50">
                    {runsState.items.map((run) => {
                      const isRunning = run.status === "RUNNING" || run.status === "PENDING";
                      const canDownloadThis = canDownload && run.status === "COMPLETED";
                      return (
                        <div
                          key={run.id}
                          className="flex items-center justify-between gap-3 rounded-full px-3 py-2.5 [transition-property:background-color] duration-150 hover:bg-white/[0.04]"
                        >
                          <div className="flex min-w-0 items-center gap-3">
                            <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-white/[0.06] text-foreground">
                              {run.kind === "DATABASE" ? (
                                <Database className="size-4" />
                              ) : (
                                <HardDrive className="size-4" />
                              )}
                            </div>
                            <div className="min-w-0">
                              <div className="flex items-center gap-2">
                                <span className="shrink-0 rounded-full border border-border bg-white/[0.04] px-2 py-0.5 text-[10.5px] font-semibold uppercase tracking-wide text-muted-foreground">
                                  {t(`backups.kind.${run.kind}`)}
                                </span>
                                <span
                                  className={`shrink-0 rounded-full border px-2 py-0.5 text-[10.5px] font-semibold uppercase tracking-wide ${STATUS_BADGE_CLASSNAME[run.status]}`}
                                >
                                  {t(`backups.status.${run.status}`)}
                                </span>
                              </div>
                              <p className="truncate font-mono text-[12px] text-muted-foreground">
                                {new Date(run.created_at).toLocaleString()} &middot; {formatBytes(run.size_bytes)}
                              </p>
                            </div>
                          </div>

                          <div className="flex shrink-0 items-center gap-2">
                            {canDownloadThis && (
                              <button
                                type="button"
                                onClick={() => void handleDownload(run)}
                                disabled={downloadingId === run.id}
                                aria-label={t("backups.runs.downloadButton")}
                                className="flex size-8 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-white/[0.06] hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50"
                              >
                                {downloadingId === run.id ? (
                                  <Loader2 className="size-4 animate-spin" />
                                ) : (
                                  <Download className="size-4" />
                                )}
                              </button>
                            )}
                            {canDeleteRun && (
                              <button
                                type="button"
                                onClick={() => setPendingDelete(run)}
                                disabled={isRunning}
                                aria-label={t("backups.runs.deleteButton")}
                                className="flex size-8 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-error/10 hover:text-error disabled:cursor-not-allowed disabled:opacity-30"
                              >
                                <Trash2 className="size-4" />
                              </button>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                  {hasMore && (
                    <div className="mt-4 flex justify-center">
                      <motion.button
                        type="button"
                        onClick={() => void handleLoadMore()}
                        disabled={isLoadingMore}
                        {...bounceTap(bounceStrength)}
                        className="flex items-center gap-1.5 rounded-full border border-border px-4 py-2 text-sm text-foreground/90 transition-colors hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        {isLoadingMore ? (
                          <Loader2 className="size-3.5 animate-spin" />
                        ) : (
                          <ChevronDown className="size-3.5" />
                        )}
                        {isLoadingMore ? t("backups.runs.loadingMore") : t("backups.runs.loadMore")}
                      </motion.button>
                    </div>
                  )}
                </>
              )}
            </>
          )}
        </div>
      )}

      {pendingDelete && (
        <ConfirmDialog
          title={t("backups.runs.deleteButton")}
          message={t("backups.runs.deleteConfirm")}
          confirmLabel={t("backups.runs.deleteConfirmButton")}
          cancelLabel={t("backups.runs.deleteCancelButton")}
          danger
          onConfirm={() => {
            void handleDelete(pendingDelete);
            setPendingDelete(null);
          }}
          onCancel={() => setPendingDelete(null)}
        />
      )}
    </div>
  );
}
