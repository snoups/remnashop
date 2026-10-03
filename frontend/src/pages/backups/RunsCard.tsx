import { AlertCircle, Download, History, Loader2, Trash2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { type BackupRun, deleteBackupRun, fetchBackupRunFile } from "@entities/backups/api";
import { usePermissions } from "@entities/user/use-current-user";
import { BACKUP_KINDS, KIND_ICON } from "@pages/backups/kinds";
import type { RunsFilter, useBackupRuns } from "@pages/backups/use-backup-runs";
import { getErrorMessage } from "@shared/api/http";
import { formatBytes } from "@shared/lib/format";
import { formatDateTime } from "@shared/lib/relative-time";
import { toast } from "@shared/lib/toast";
import { Badge, type BadgeTone } from "@shared/ui/Badge";
import { Button } from "@shared/ui/Button";
import { Card } from "@shared/ui/Card";
import { CardHeader } from "@shared/ui/CardHeader";
import { LIST_BODY_CLASS } from "@shared/ui/classes";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { EmptyState } from "@shared/ui/EmptyState";
import { IconButton } from "@shared/ui/IconButton";
import { LoadMoreButton } from "@shared/ui/LoadMoreButton";
import { PillTabs } from "@shared/ui/PillTabs";
import { Spinner } from "@shared/ui/Spinner";

const RUNS_FILTERS: RunsFilter[] = ["ALL", ...BACKUP_KINDS];

const STATUS_BADGE_TONE: Record<BackupRun["status"], BadgeTone> = {
  COMPLETED: "success",
  RUNNING: "warning",
  PENDING: "neutral",
  FAILED: "error",
};

export function RunsCard({
  runs,
  onStatsChanged,
}: {
  runs: ReturnType<typeof useBackupRuns>;
  onStatsChanged: () => void;
}) {
  const { t, i18n } = useTranslation();
  const [downloadingId, setDownloadingId] = useState<number | null>(null);
  const [pendingDelete, setPendingDelete] = useState<BackupRun | null>(null);
  const { state: runsState, filter, setFilter, isLoadingMore, hasMore, loadMore: handleLoadMore } = runs;

  const permissions = usePermissions();
  const canDownload = permissions.includes("BACKUPS_RUN_DOWNLOAD");
  const canDeleteRun = permissions.includes("BACKUPS_RUN_DELETE");

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
      runs.remove(run);
      onStatsChanged();
    } catch (err) {
      toast.error(getErrorMessage(err, t("backups.runs.deleteError")));
    }
  };

  const formatDuration = (run: BackupRun): string | null => {
    if (run.finished_at === null) return null;
    const total = Math.max(
      0,
      Math.round((new Date(run.finished_at).getTime() - new Date(run.created_at).getTime()) / 1000),
    );
    if (total < 1) return t("backups.runs.durationUnderSecond");
    return total < 60
      ? t("backups.runs.durationSeconds", { seconds: total })
      : t("backups.runs.durationMinutes", { minutes: Math.floor(total / 60), seconds: total % 60 });
  };

  return (
    <>
      <Card className="flex flex-col">
        <CardHeader
          icon={History}
          title={t("backups.runs.title")}
          description={t("backups.runs.description")}
          aside={
            <div className="shrink-0">
              <PillTabs
                items={RUNS_FILTERS.map((value) => ({
                  key: value,
                  label: value === "ALL" ? t("backups.runs.filterAll") : t(`backups.kind.${value}`),
                }))}
                activeKey={filter}
                onSelect={setFilter}
              />
            </div>
          }
        />

        {runsState.kind === "loading" && <Spinner size="page" />}
        {runsState.kind === "error" && (
          <div className="flex flex-col items-center gap-2 py-12 text-error">
            <AlertCircle className="size-5" />
            <p className="text-sm">{t("backups.loadError")}</p>
          </div>
        )}
        {runsState.kind === "ready" && runsState.items.length === 0 && (
          <EmptyState text={t("backups.empty")} size="page" />
        )}
        {runsState.kind === "ready" && runsState.items.length > 0 && (
          <>
            <div className={`mt-4 ${LIST_BODY_CLASS}`}>
              {runsState.items.map((run) => {
                const Icon = KIND_ICON[run.kind];
                const isRunning = run.status === "RUNNING" || run.status === "PENDING";
                const canDownloadThis = canDownload && run.status === "COMPLETED";
                const duration = formatDuration(run);
                const meta = [
                  formatDateTime(run.created_at, i18n.language),
                  run.size_bytes === null ? "—" : formatBytes(run.size_bytes, i18n.language),
                  ...(duration === null ? [] : [duration]),
                ].join(" · ");
                return (
                  <div
                    key={run.id}
                    className="flex items-center justify-between gap-3 rounded-full px-[15px] py-2.5 transition-colors hover:bg-white/[0.04]"
                  >
                    <div className="flex min-w-0 items-center gap-3">
                      <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-white/[0.06] text-foreground">
                        <Icon className="size-4" />
                      </div>
                      <div className="flex min-w-0 flex-col gap-0.5">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-[13.5px] font-semibold text-foreground">
                            {t(`backups.kind.${run.kind}`)}
                          </span>
                          <Badge tone={STATUS_BADGE_TONE[run.status]}>
                            {isRunning && <Loader2 className="size-3 animate-spin" />}
                            {t(`backups.status.${run.status}`)}
                          </Badge>
                          <Badge>
                            {run.triggered_by === null
                              ? t("backups.runs.triggerSchedule")
                              : t("backups.runs.triggerManual")}
                          </Badge>
                        </div>
                        <p className="truncate font-mono text-[12px] text-muted-foreground">{meta}</p>
                        {run.status === "FAILED" && run.error && (
                          <p className="flex min-w-0 items-center gap-1.5 text-xs text-error">
                            <AlertCircle className="size-3 shrink-0" />
                            <span className="truncate">{run.error}</span>
                          </p>
                        )}
                      </div>
                    </div>

                    <div className="flex shrink-0 items-center gap-1">
                      {canDownloadThis && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => void handleDownload(run)}
                          disabled={downloadingId === run.id}
                        >
                          {downloadingId === run.id ? (
                            <Loader2 className="size-3.5 animate-spin" />
                          ) : (
                            <Download className="size-3.5" />
                          )}
                          <span className="hidden sm:inline">{t("backups.runs.downloadButton")}</span>
                        </Button>
                      )}
                      {canDeleteRun && (
                        <IconButton
                          size="8"
                          tone="danger"
                          bounce={0.05}
                          onClick={() => setPendingDelete(run)}
                          disabled={isRunning}
                        >
                          <Trash2 className="size-4" />
                        </IconButton>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>

            {runsState.kind === "ready" && hasMore && (
              <div className="mt-4">
                <LoadMoreButton
                  onClick={() => void handleLoadMore()}
                  isLoading={isLoadingMore}
                  shown={runsState.items.length}
                  total={runsState.total}
                />
              </div>
            )}
          </>
        )}
      </Card>

      {pendingDelete && (
        <ConfirmDialog
          title={t("backups.runs.deleteConfirmTitle")}
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
    </>
  );
}
