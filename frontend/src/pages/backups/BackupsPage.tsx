import {
  AlertCircle,
  Clock,
  Database,
  Download,
  HardDrive,
  History,
  Loader2,
  Play,
  ShieldCheck,
  Trash2,
} from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useRef, useState, type ComponentType, type FormEvent, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";

import {
  type BackupKind,
  type BackupRun,
  type BackupStats,
  createBackupRun,
  DEFAULT_PAGE_SIZE,
  deleteBackupRun,
  fetchBackupRunFile,
  getBackupSettings,
  getBackupStats,
  listBackupRuns,
  resetBackupSettings,
  updateBackupSettings,
} from "@entities/backups/api";
import { useCurrentUser } from "@entities/user/use-current-user";
import { PillTabs } from "@features/dialog-canvas-editor/PillTabs";
import { getErrorMessage } from "@shared/api/http";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { blockNonIntegerKeys, parseRequiredInt } from "@shared/lib/number-input";
import { formatDateTime, formatRelative } from "@shared/lib/relative-time";
import { toast } from "@shared/lib/toast";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { EmptyState } from "@shared/ui/EmptyState";
import { FieldHint } from "@shared/ui/FieldHint";
import { LoadMoreButton } from "@shared/ui/LoadMoreButton";
import { Spinner } from "@shared/ui/Spinner";
import { Switch } from "@shared/ui/Switch";
import { Button } from "@shared/ui/Button";
import { Badge, type BadgeTone } from "@shared/ui/Badge";
import { TextInput } from "@shared/ui/TextInput";
import { Card } from "@shared/ui/Card";
import { Field } from "@shared/ui/Field";
import { ChoiceChip } from "@shared/ui/ChoiceChip";
import { EYEBROW_CLASS, LIST_BODY_CLASS } from "@shared/ui/classes";
import { IconButton } from "@shared/ui/IconButton";

type SettingsState = { kind: "loading" } | { kind: "error" } | { kind: "ready"; savedEnabled: boolean };
type RunsState =
  | { kind: "loading" }
  | { kind: "error" }
  | { kind: "ready"; items: BackupRun[]; total: number };
type RunsFilter = BackupKind | "ALL";

const BACKUP_KINDS: BackupKind[] = ["DATABASE", "ASSETS"];
const RUNS_FILTERS: RunsFilter[] = ["ALL", ...BACKUP_KINDS];
const INTERVAL_PRESETS = [6, 12, 24, 48];
// plain polling, switch to SSE/websocket if the run list grows hot
const RUNS_POLL_INTERVAL_MS = 5000;
// the list endpoint caps page_size at 200
const RUNS_MAX_PAGE_SIZE = 200;
const MAX_FILES_PRESETS = [3, 7, 14, 30];


const KIND_ICON: Record<BackupKind, ComponentType<{ className?: string }>> = {
  DATABASE: Database,
  ASSETS: HardDrive,
};

const STATUS_BADGE_TONE: Record<BackupRun["status"], BadgeTone> = {
  COMPLETED: "success",
  RUNNING: "warning",
  PENDING: "neutral",
  FAILED: "error",
};

function formatBytes(t: TFunction, bytes: number | null): string {
  if (bytes === null) return "—";
  const unitKeys = ["byte", "kilobyte", "megabyte", "gigabyte", "terabyte"];
  if (bytes < 1024) return `${bytes} ${t(`backups.units.${unitKeys[0]}`)}`;
  let value = bytes / 1024;
  let unitIndex = 1;
  while (value >= 1024 && unitIndex < unitKeys.length - 1) {
    value /= 1024;
    unitIndex++;
  }
  return `${value.toFixed(1)} ${t(`backups.units.${unitKeys[unitIndex]}`)}`;
}

function CardHeader({
  icon: Icon,
  title,
  description,
  aside,
}: {
  icon: ComponentType<{ className?: string }>;
  title: string;
  description: string;
  aside?: ReactNode;
}) {
  return (
    <>
      <div className="flex flex-wrap items-center gap-2.5">
        <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] text-foreground backdrop-blur-md">
          <Icon className="size-4" />
        </div>
        <div className="min-w-0 flex-1">
          <h2 className="text-sm font-bold text-foreground">{title}</h2>
          <p className="mt-0.5 text-[12.5px] text-muted-foreground">{description}</p>
        </div>
        {aside}
      </div>
      <div className="-mx-4 mt-4 border-t border-white/[0.07]" />
    </>
  );
}

function TimelineItem({
  icon: Icon,
  tone,
  label,
  value,
  detail,
}: {
  icon: ComponentType<{ className?: string }>;
  tone: string;
  label: string;
  value: string;
  detail?: string;
}) {
  return (
    <div className="flex min-w-0 flex-1 items-center gap-2.5">
      <div className={`flex size-8 shrink-0 items-center justify-center rounded-full ${tone}`}>
        <Icon className="size-4" />
      </div>
      <div className="min-w-0">
        <div className={EYEBROW_CLASS}>{label}</div>
        <div className="truncate text-[13.5px] font-semibold text-foreground">{value}</div>
        {detail && <div className="truncate text-xs text-muted-foreground">{detail}</div>}
      </div>
    </div>
  );
}

function PresetButtons({
  values,
  current,
  onPick,
  format,
  disabled,
}: {
  values: number[];
  current: string;
  onPick: (value: string) => void;
  format: (value: number) => string;
  disabled: boolean;
}) {
  return (
    <div className="grid grid-cols-4 gap-1.5">
      {values.map((value) => {
        const isActive = current === String(value);
        return (
          <ChoiceChip
            key={value}
            onClick={() => onPick(String(value))}
            aria-pressed={isActive}
            disabled={disabled}
            active={isActive}
            size="sm"
          >
            {format(value)}
          </ChoiceChip>
        );
      })}
    </div>
  );
}

export function BackupsPage() {
  const { t, i18n } = useTranslation();
  const bounceStrength = useBounceStrength();

  const [settingsState, setSettingsState] = useState<SettingsState>({ kind: "loading" });
  const [isSavingSettings, setIsSavingSettings] = useState(false);
  const [enabled, setEnabled] = useState(false);
  const [intervalHours, setIntervalHours] = useState("24");
  const [maxFiles, setMaxFiles] = useState("14");
  const [runKind, setRunKind] = useState<BackupKind>("DATABASE");
  const [isStartingRun, setIsStartingRun] = useState(false);
  const [stats, setStats] = useState<BackupStats | null>(null);

  const [runsState, setRunsState] = useState<RunsState>({ kind: "loading" });
  const [filter, setFilter] = useState<RunsFilter>("ALL");
  const [page, setPage] = useState(1);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [downloadingId, setDownloadingId] = useState<number | null>(null);
  const [pendingDelete, setPendingDelete] = useState<BackupRun | null>(null);
  const [isResetConfirmOpen, setIsResetConfirmOpen] = useState(false);
  const [isResettingSettings, setIsResettingSettings] = useState(false);

  const currentUserState = useCurrentUser();
  const permissions =
    currentUserState.kind === "ready" ? currentUserState.data.effective_permissions : [];
  const canManageSettings = permissions.includes("BACKUPS_SETTINGS_MANAGE");
  const canResetSettings = permissions.includes("BACKUPS_SETTINGS_RESET");
  const canCreateRun = permissions.includes("BACKUPS_RUN_CREATE");
  const canDownload = permissions.includes("BACKUPS_RUN_DOWNLOAD");
  const canDeleteRun = permissions.includes("BACKUPS_RUN_DELETE");
  const canViewRuns = permissions.includes("BACKUPS_RUN_VIEW");
  const canViewStats = permissions.includes("BACKUPS_STATS_VIEW");

  const kindFilter = (value: RunsFilter) => (value === "ALL" ? undefined : value);

  const loadStats = (signal?: AbortSignal) => {
    if (!canViewStats) return;
    getBackupStats(signal)
      .then((result) => {
        if (!signal?.aborted) setStats(result);
      })
      .catch(() => {
        // stats are decorative; the rest of the page stays usable without them
      });
  };

  const loadRuns = (value: RunsFilter, signal?: AbortSignal) => {
    setPage(1);
    listBackupRuns({ kind: kindFilter(value), page: 1, pageSize: DEFAULT_PAGE_SIZE }, signal)
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
        setSettingsState({ kind: "ready", savedEnabled: settings.enabled });
      })
      .catch(() => {
        if (!controller.signal.aborted) setSettingsState({ kind: "error" });
      });

    loadStats(controller.signal);
    if (canViewRuns) loadRuns("ALL", controller.signal);
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const runsRef = useRef(runsState);
  runsRef.current = runsState;

  // refetches every row already loaded, so status changes and new scheduled
  // runs show up without a reload; skipped while the tab is hidden
  useEffect(() => {
    if (!canViewRuns) return;
    let cancelled = false;
    const timer = setInterval(() => {
      const current = runsRef.current;
      if (document.hidden || current.kind !== "ready") return;
      const pageSize = Math.min(RUNS_MAX_PAGE_SIZE, Math.max(DEFAULT_PAGE_SIZE, current.items.length));
      listBackupRuns({ kind: kindFilter(filter), page: 1, pageSize })
        .then((result) => {
          if (cancelled) return;
          const wasActive = current.items.some((run) => run.status === "PENDING" || run.status === "RUNNING");
          const isActive = result.items.some((run) => run.status === "PENDING" || run.status === "RUNNING");
          setRunsState({ kind: "ready", items: result.items, total: result.total });
          if (wasActive && !isActive) loadStats();
        })
        .catch(() => {
          // next tick retries
        });
    }, RUNS_POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filter, canViewRuns]);

  const handleFilterChange = (value: RunsFilter) => {
    if (value === filter) return;
    setFilter(value);
    setRunsState({ kind: "loading" });
    loadRuns(value);
  };

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
      setSettingsState({ kind: "ready", savedEnabled: settings.enabled });
      loadStats();
      toast.success(t("backups.schedule.saved"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("backups.schedule.error")));
    } finally {
      setIsSavingSettings(false);
    }
  };

  const handleResetSettings = async () => {
    setIsResettingSettings(true);
    try {
      const settings = await resetBackupSettings();
      setEnabled(settings.enabled);
      setIntervalHours(String(settings.interval_hours));
      setMaxFiles(String(settings.max_files));
      setSettingsState({ kind: "ready", savedEnabled: settings.enabled });
      loadStats();
      toast.success(t("backups.schedule.resetSuccess"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("backups.schedule.resetError")));
    } finally {
      setIsResettingSettings(false);
    }
  };

  const handleRunNow = async () => {
    setIsStartingRun(true);
    try {
      const run = await createBackupRun(runKind);
      toast.success(t("backups.manual.runStarted"));
      if (runsState.kind === "ready" && (filter === "ALL" || filter === run.kind)) {
        setRunsState({ kind: "ready", items: [run, ...runsState.items], total: runsState.total + 1 });
      }
    } catch (err) {
      toast.error(getErrorMessage(err, t("backups.manual.runError")));
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
      const result = await listBackupRuns({
        kind: kindFilter(filter),
        page: nextPage,
        pageSize: DEFAULT_PAGE_SIZE,
      });
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
      loadStats();
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

  const hasMore = runsState.kind === "ready" && runsState.items.length < runsState.total;
  const lastBackup = stats?.last_database_backup ?? null;
  const lastBackupAt = lastBackup === null ? null : (lastBackup.finished_at ?? lastBackup.created_at);
  const dimmed = enabled ? "" : "opacity-40";

  return (
    <div className="flex flex-col gap-4">
      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="flex flex-col">
          <CardHeader
            icon={Database}
            title={t("backups.schedule.title")}
            description={t("backups.schedule.description")}
            aside={
              settingsState.kind === "ready" && (
                <span
                  className={`flex h-9 shrink-0 items-center rounded-full px-4 text-[13px] font-semibold ${
                    settingsState.savedEnabled
                      ? "bg-success/10 text-success"
                      : "bg-white/[0.05] text-muted-foreground"
                  }`}
                >
                  {settingsState.savedEnabled ? t("backups.schedule.badgeOn") : t("backups.schedule.badgeOff")}
                </span>
              )
            }
          />

          {settingsState.kind === "loading" && <Spinner size="card" />}
          {settingsState.kind === "error" && (
            <div className="flex flex-col items-center gap-2 py-10 text-error">
              <AlertCircle className="size-5" />
              <p className="text-sm">{t("backups.loadError")}</p>
            </div>
          )}
          {settingsState.kind === "ready" && (
            <form
              onSubmit={(event) => void handleSaveSettings(event)}
              className="mt-4 flex flex-1 flex-col gap-3.5"
            >
              <div className="flex items-center justify-between gap-3 py-1">
                <span className="flex items-center gap-1.5 text-sm text-foreground/80">
                  {t("backups.schedule.enabledLabel")}
                  <FieldHint text={t("backups.schedule.enabledHint")} />
                </span>
                <Switch
                  checked={enabled}
                  onChange={setEnabled}
                  disabled={!canManageSettings}
                  ariaLabel={t("backups.schedule.enabledLabel")}
                />
              </div>

              <div className="flex flex-wrap gap-4">
                <Field label={t("backups.schedule.intervalLabel")} htmlFor="backups-interval" info={t("backups.schedule.intervalHint")} className="min-w-40 flex-1">
                  <div className={`flex flex-col gap-1.5 transition-opacity ${dimmed}`}>
                    <div className="relative">
                      <TextInput
                        id="backups-interval"
                        type="number"
                        onKeyDown={blockNonIntegerKeys}
                        min={1}
                        step="1"
                        value={intervalHours}
                        onChange={(event) => setIntervalHours(event.target.value)}
                        disabled={!canManageSettings || !enabled}
                        className="w-full"
                      />
                    </div>
                    {canManageSettings && (
                      <PresetButtons
                        values={INTERVAL_PRESETS}
                        current={intervalHours}
                        onPick={setIntervalHours}
                        format={(hours) => t("backups.schedule.preset", { hours })}
                        disabled={!enabled}
                      />
                    )}
                  </div>
                </Field>
                <Field label={t("backups.schedule.maxFilesLabel")} htmlFor="backups-max-files" info={t("backups.schedule.maxFilesHint")} className="min-w-40 flex-1">
                  <div className={`flex flex-col gap-1.5 transition-opacity ${dimmed}`}>
                    <div className="relative">
                      <TextInput
                        id="backups-max-files"
                        type="number"
                        onKeyDown={blockNonIntegerKeys}
                        min={1}
                        step="1"
                        value={maxFiles}
                        onChange={(event) => setMaxFiles(event.target.value)}
                        disabled={!canManageSettings || !enabled}
                        className="w-full"
                      />
                    </div>
                    {canManageSettings && (
                      <PresetButtons
                        values={MAX_FILES_PRESETS}
                        current={maxFiles}
                        onPick={setMaxFiles}
                        format={String}
                        disabled={!enabled}
                      />
                    )}
                  </div>
                </Field>
              </div>

              {canViewStats && stats !== null && (
                <div className="flex flex-wrap items-center gap-3.5 rounded-xl bg-white/[0.03] p-3">
                  <TimelineItem
                    icon={Clock}
                    tone="bg-accent text-primary"
                    label={t("backups.schedule.nextRun")}
                    value={stats.next_run_at === null ? "—" : formatDateTime(stats.next_run_at, i18n.language)}
                    detail={
                      stats.next_run_at === null ? undefined : formatRelative(stats.next_run_at, i18n.language)
                    }
                  />
                  <div className="hidden w-px self-stretch bg-white/[0.07] sm:block" />
                  <TimelineItem
                    icon={ShieldCheck}
                    tone="bg-success/10 text-success"
                    label={t("backups.schedule.lastBackup")}
                    value={lastBackupAt === null ? "—" : formatDateTime(lastBackupAt, i18n.language)}
                    detail={lastBackupAt === null ? undefined : formatRelative(lastBackupAt, i18n.language)}
                  />
                </div>
              )}

              {(canManageSettings || canResetSettings) && (
                <div className="mt-auto flex items-center gap-2">
                  {canManageSettings && (
                    <Button
                      variant="accent"
                      className="w-fit"
                      type="submit"
                      disabled={isSavingSettings}
                    >
                      {isSavingSettings ? t("backups.schedule.saving") : t("backups.schedule.save")}
                    </Button>
                  )}
                  {canResetSettings && (
                    <Button
                      variant="outline"
                      className="w-fit"
                      type="button"
                      onClick={() => setIsResetConfirmOpen(true)}
                      disabled={isResettingSettings}
                    >
                      {t("backups.schedule.reset")}
                    </Button>
                  )}
                </div>
              )}
            </form>
          )}
        </Card>

        {(canCreateRun || canViewStats) && (
          <Card className="flex flex-col">
            <CardHeader
              icon={Play}
              title={t("backups.manual.title")}
              description={t("backups.manual.description")}
            />

            <div className="mt-4 flex flex-1 flex-col gap-3.5">
              {canCreateRun && (
                <>
                  <span className={EYEBROW_CLASS}>{t("backups.manual.kindLabel")}</span>
                  <div
                    role="radiogroup"
                    aria-label={t("backups.manual.kindLabel")}
                    className="grid gap-2.5 sm:grid-cols-2"
                  >
                    {BACKUP_KINDS.map((kind) => {
                      const Icon = KIND_ICON[kind];
                      const isActive = runKind === kind;
                      return (
                        <motion.button
                          key={kind}
                          type="button"
                          {...bounceTap(bounceStrength)}
                          role="radio"
                          aria-checked={isActive}
                          onClick={() => setRunKind(kind)}
                          className={`flex items-start gap-3 rounded-[14px] border p-3.5 text-left transition-colors ${
                            isActive
                              ? "border-primary/45 bg-primary/[0.07]"
                              : "border-white/[0.08] bg-white/[0.02] hover:bg-white/[0.04]"
                          }`}
                        >
                          <div
                            className={`flex size-9 shrink-0 items-center justify-center rounded-full transition-colors ${
                              isActive ? "bg-primary/15 text-primary" : "bg-white/[0.06] text-foreground"
                            }`}
                          >
                            <Icon className="size-[18px]" />
                          </div>
                          <div className="flex min-w-0 flex-col gap-0.5">
                            <span className="text-sm font-semibold text-foreground">{t(`backups.kind.${kind}`)}</span>
                            <span className="text-xs text-muted-foreground">
                              {t(`backups.kindDescription.${kind}`)}
                            </span>
                          </div>
                        </motion.button>
                      );
                    })}
                  </div>

                  <div className="flex items-center gap-2">
                    <Button
                      variant="accent"
                      className="w-fit"
                      type="button"
                      onClick={() => void handleRunNow()}
                      disabled={isStartingRun}
                    >
                      {isStartingRun ? <Loader2 className="size-3.5 animate-spin" /> : <Play className="size-3.5" />}
                      {t("backups.manual.runNow")}
                    </Button>
                    <FieldHint text={t("backups.manual.runHint")} />
                  </div>
                </>
              )}

              {canViewStats && stats !== null && (
                <div
                  className={`mt-auto flex flex-col gap-2.5 ${canCreateRun ? "border-t border-white/[0.06] pt-4" : ""}`}
                >
                  <span className={EYEBROW_CLASS}>{t("backups.manual.storageLabel")}</span>
                  <div className="grid grid-cols-3 gap-2">
                    <div className="rounded-xl bg-white/[0.03] px-3 py-2.5">
                      <div className="text-xs text-muted-foreground">{t("backups.manual.statCompleted")}</div>
                      <div className="mt-0.5 text-lg font-bold text-foreground">{stats.completed_count}</div>
                    </div>
                    <div className="rounded-xl bg-white/[0.03] px-3 py-2.5">
                      <div className="text-xs text-muted-foreground">{t("backups.manual.statSize")}</div>
                      <div className="mt-0.5 text-lg font-bold text-foreground">
                        {formatBytes(t, stats.total_size_bytes)}
                      </div>
                    </div>
                    <div className="rounded-xl bg-white/[0.03] px-3 py-2.5">
                      <div className="text-xs text-muted-foreground">{t("backups.manual.statFailed")}</div>
                      <div
                        className={`mt-0.5 text-lg font-bold ${stats.failed_count > 0 ? "text-error" : "text-foreground"}`}
                      >
                        {stats.failed_count}
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </Card>
        )}
      </div>

      {canViewRuns && (
        <Card className="flex flex-col">
          <CardHeader
            icon={History}
            title={t("backups.runs.title")}
            description={t("backups.runs.description")}
            aside={
              <div role="group" aria-label={t("backups.runs.filterLabel")} className="shrink-0">
                <PillTabs
                  items={RUNS_FILTERS.map((value) => ({
                    key: value,
                    label: value === "ALL" ? t("backups.runs.filterAll") : t(`backups.kind.${value}`),
                  }))}
                  activeKey={filter}
                  onSelect={handleFilterChange}
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
                    formatBytes(t, run.size_bytes),
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
                            aria-label={t("backups.runs.deleteButton")}
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
      )}

      {isResetConfirmOpen && (
        <ConfirmDialog
          title={t("backups.schedule.resetConfirmTitle")}
          message={t("backups.schedule.resetConfirmMessage")}
          confirmLabel={t("backups.schedule.reset")}
          cancelLabel={t("backups.runs.deleteCancelButton")}
          danger
          onConfirm={() => {
            setIsResetConfirmOpen(false);
            void handleResetSettings();
          }}
          onCancel={() => setIsResetConfirmOpen(false)}
        />
      )}

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
    </div>
  );
}
