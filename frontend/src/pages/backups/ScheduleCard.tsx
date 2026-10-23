import { Clock, Database, ShieldCheck } from "lucide-react";
import { useState, type ComponentType, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import {
  type BackupSettings,
  type BackupStats,
  getBackupSettings,
  resetBackupSettings,
  updateBackupSettings,
} from "@entities/backups/api";
import { usePermissions } from "@entities/user/use-current-user";
import { getErrorMessage } from "@shared/api/http";
import { blockNonIntegerKeys, parseRequiredInt } from "@shared/lib/number-input";
import { formatDateTime, formatRelative } from "@shared/lib/relative-time";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { Button } from "@shared/ui/Button";
import { Card } from "@shared/ui/Card";
import { CardHeader } from "@shared/ui/CardHeader";
import { ChoiceChip } from "@shared/ui/ChoiceChip";
import { EYEBROW_CLASS } from "@shared/ui/classes";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { ErrorState } from "@shared/ui/EmptyState";
import { Field } from "@shared/ui/Field";
import { FieldHint } from "@shared/ui/FieldHint";
import { Spinner } from "@shared/ui/Spinner";
import { Switch } from "@shared/ui/Switch";
import { TextInput } from "@shared/ui/TextInput";

const INTERVAL_PRESETS = [6, 12, 24, 48];
const MAX_FILES_PRESETS = [3, 7, 14, 30];

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
        <div className="truncate text-[13px] font-semibold text-foreground">{value}</div>
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

export function ScheduleCard({ stats, onStatsChanged }: { stats: BackupStats | null; onStatsChanged: () => void }) {
  const { t, i18n } = useTranslation();
  const [isSavingSettings, setIsSavingSettings] = useState(false);
  const [enabled, setEnabled] = useState(false);
  const [intervalHours, setIntervalHours] = useState("24");
  const [maxFiles, setMaxFiles] = useState("14");
  const [savedEnabled, setSavedEnabled] = useState(false);
  const [isResetConfirmOpen, setIsResetConfirmOpen] = useState(false);
  const [isResettingSettings, setIsResettingSettings] = useState(false);

  const permissions = usePermissions();
  const canManageSettings = permissions.includes("BACKUPS_SETTINGS_MANAGE");
  const canResetSettings = permissions.includes("BACKUPS_SETTINGS_RESET");
  const canViewStats = permissions.includes("BACKUPS_STATS_VIEW");

  const applySettings = (settings: BackupSettings) => {
    setEnabled(settings.enabled);
    setIntervalHours(String(settings.interval_hours));
    setMaxFiles(String(settings.max_files));
    setSavedEnabled(settings.enabled);
  };
  const [settingsState] = useAsyncResource(getBackupSettings, { onSuccess: applySettings });

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
      applySettings(
        await updateBackupSettings({ enabled, interval_hours: parsedIntervalHours, max_files: parsedMaxFiles }),
      );
      onStatsChanged();
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
      applySettings(await resetBackupSettings());
      onStatsChanged();
      toast.success(t("backups.schedule.resetSuccess"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("backups.schedule.resetError")));
    } finally {
      setIsResettingSettings(false);
    }
  };

  const lastBackup = stats?.last_database_backup ?? null;
  const lastBackupAt = lastBackup === null ? null : (lastBackup.finished_at ?? lastBackup.created_at);
  const dimmed = enabled ? "" : "opacity-40";

  return (
    <>
      <Card className="flex flex-col">
        <CardHeader
          icon={Database}
          title={t("backups.schedule.title")}
          description={t("backups.schedule.description")}
          aside={
            settingsState.kind === "ready" && (
              <span
                className={`flex h-9 shrink-0 items-center rounded-full px-4 text-[13px] font-semibold ${
                  savedEnabled
                    ? "bg-success/10 text-success"
                    : "bg-white/[0.05] text-muted-foreground"
                }`}
              >
                {savedEnabled ? t("backups.schedule.badgeOn") : t("backups.schedule.badgeOff")}
              </span>
            )
          }
        />

        {settingsState.kind === "loading" && <Spinner size="card" />}
        {settingsState.kind === "error" && (
          <ErrorState text={t("common.loadError")} />
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
                    {isSavingSettings ? t("common.saving") : t("common.save")}
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
                    {t("common.reset")}
                  </Button>
                )}
              </div>
            )}
          </form>
        )}
      </Card>

      {isResetConfirmOpen && (
        <ConfirmDialog
          title={t("backups.schedule.resetConfirmTitle")}
          message={t("backups.schedule.resetConfirmMessage")}
          confirmLabel={t("common.reset")}
          cancelLabel={t("common.cancel")}
          danger
          onConfirm={() => {
            setIsResetConfirmOpen(false);
            void handleResetSettings();
          }}
          onCancel={() => setIsResetConfirmOpen(false)}
        />
      )}
    </>
  );
}
