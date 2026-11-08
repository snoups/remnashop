import { History, Loader2, Square, Trash2, X } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { type BackupRun, cancelBackupRun, deleteBackupRun, fetchBackupRunFile } from "@entities/backups/api";
import { usePermissions } from "@entities/user/use-current-user";
import { BACKUP_KINDS, KIND_ICON } from "@pages/backups/kinds";
import type { RunsFilter, useBackupRuns } from "@pages/backups/use-backup-runs";
import { getErrorMessage } from "@shared/api/http";
import { formatBytes } from "@shared/lib/format";
import { formatDateTime } from "@shared/lib/relative-time";
import { toast } from "@shared/lib/toast";
import { Badge, type BadgeTone } from "@shared/ui/Badge";
import { Button } from "@shared/ui/Button";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { FieldHint } from "@shared/ui/FieldHint";
import { EmptyState, ErrorState } from "@shared/ui/glass/EmptyState";
import { Row } from "@shared/ui/glass/Row";
import { Section, SectionRows } from "@shared/ui/glass/Section";
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
  CANCELED: "neutral",
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
  const [pendingCancel, setPendingCancel] = useState<BackupRun | null>(null);
  const { state: runsState, filter, setFilter, isLoadingMore, hasMore, loadMore: handleLoadMore } = runs;

  const permissions = usePermissions();
  const canDownload = permissions.includes("BACKUPS_RUN_DOWNLOAD");
  const canDeleteRun = permissions.includes("BACKUPS_RUN_DELETE");
  const canCancelRun = permissions.includes("BACKUPS_RUN_CANCEL");

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

  const handleCancel = async (run: BackupRun) => {
    try {
      runs.replace(await cancelBackupRun(run.id));
      onStatsChanged();
    } catch (err) {
      toast.error(getErrorMessage(err, t("backups.runs.cancelError")));
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
      <Section
        icon={History}
        title={t("backups.runs.title")}
        description={t("backups.runs.description")}
        aside={
          <PillTabs
            items={RUNS_FILTERS.map((value) => ({
              key: value,
              label: value === "ALL" ? t("backups.runs.filterAll") : t(`backups.kind.${value}`),
            }))}
            activeKey={filter}
            onSelect={setFilter}
          />
        }
      >
        {runsState.kind === "loading" && <Spinner size="card" />}
        {runsState.kind === "error" && <ErrorState text={t("common.loadError")} />}
        {runsState.kind === "ready" && runsState.items.length === 0 && <EmptyState text={t("backups.empty")} />}
        {runsState.kind === "ready" && runsState.items.length > 0 && (
          <>
            <SectionRows>
              {runsState.items.map((run) => {
                const isRunning = run.status === "RUNNING" || run.status === "PENDING";
                const canDownloadThis = canDownload && run.status === "COMPLETED";
                const duration = formatDuration(run);
                const meta = [
                  formatDateTime(run.created_at, i18n.language),
                  ...(run.size_bytes === null ? [] : [formatBytes(run.size_bytes, i18n.language)]),
                  ...(duration === null ? [] : [duration]),
                ].join(" · ");
                return (
                  <Row
                    key={run.id}
                    icon={KIND_ICON[run.kind]}
                    label={
                      <>
                        {t(`backups.kind.${run.kind}`)}
                        {run.status === "FAILED" && run.error ? (
                          <FieldHint
                            text={run.error}
                            side="bottom"
                            error
                            trigger={
                              <Badge tone="error" className="cursor-help">
                                {t(`backups.status.${run.status}`)}
                              </Badge>
                            }
                          />
                        ) : (
                          <Badge tone={STATUS_BADGE_TONE[run.status]}>
                            {isRunning && <Loader2 className="size-3 animate-spin" />}
                            {t(`backups.status.${run.status}`)}
                          </Badge>
                        )}
                        <Badge>
                          {run.triggered_by === null
                            ? t("backups.runs.triggerSchedule")
                            : t("backups.runs.triggerManual")}
                        </Badge>
                      </>
                    }
                    description={<p className="truncate">{meta}</p>}
                  >
                    {canDownloadThis && (
                      <Button
                        variant="glass"
                        size="sm"
                        onClick={() => void handleDownload(run)}
                        isLoading={downloadingId === run.id}
                      >
                        {t("backups.runs.downloadButton")}
                      </Button>
                    )}
                    {isRunning
                      ? canCancelRun && (
                          <Button
                            variant="glassDanger"
                            size="sm"
                            icon={run.status === "PENDING" ? X : Square}
                            onClick={() => setPendingCancel(run)}
                          >
                            {t(run.status === "PENDING" ? "backups.runs.dequeueButton" : "backups.runs.stopButton")}
                          </Button>
                        )
                      : canDeleteRun && (
                          <IconButton size="8" tone="danger" onClick={() => setPendingDelete(run)}>
                            <Trash2 className="size-4" />
                          </IconButton>
                        )}
                  </Row>
                );
              })}
            </SectionRows>

            {hasMore && (
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
      </Section>

      {pendingCancel && (
        <ConfirmDialog
          title={t(pendingCancel.status === "PENDING" ? "backups.runs.dequeueConfirmTitle" : "backups.runs.stopConfirmTitle")}
          message={t(pendingCancel.status === "PENDING" ? "backups.runs.dequeueConfirm" : "backups.runs.stopConfirm")}
          confirmLabel={t(pendingCancel.status === "PENDING" ? "backups.runs.dequeueButton" : "backups.runs.stopButton")}
          cancelLabel={t("common.cancel")}
          danger
          onConfirm={() => {
            void handleCancel(pendingCancel);
            setPendingCancel(null);
          }}
          onCancel={() => setPendingCancel(null)}
        />
      )}

      {pendingDelete && (
        <ConfirmDialog
          title={t("backups.runs.deleteConfirmTitle")}
          message={t("backups.runs.deleteConfirm")}
          confirmLabel={t("common.delete")}
          cancelLabel={t("common.cancel")}
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
