import { Clock, Database, Power, ShieldCheck } from "lucide-react";
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
import { GLASS_INNER_CARD_CLASS } from "@shared/ui/classes";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { ErrorState } from "@shared/ui/glass/EmptyState";
import { Field } from "@shared/ui/glass/Field";
import { Input } from "@shared/ui/glass/Input";
import { Row } from "@shared/ui/glass/Row";
import { Section, SectionRows } from "@shared/ui/glass/Section";
import { StatusPill } from "@shared/ui/glass/StatusPill";
import { Switch } from "@shared/ui/glass/Switch";
import { PillTabs } from "@shared/ui/PillTabs";
import { SaveFooter } from "@shared/ui/SaveFooter";
import { Spinner } from "@shared/ui/Spinner";

const MAX_INTERVAL_HOURS = 8760;
const MAX_FILES = 365;
const INNER_CARD_CLASS = `gap-3 p-3.5 ${GLASS_INNER_CARD_CLASS}`;
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
    <div className="flex min-w-0 flex-1 basis-44 items-center gap-2.5">
      <div className={`flex size-8 shrink-0 items-center justify-center rounded-full ${tone}`}>
        <Icon className="size-4" />
      </div>
      <div className="min-w-0">
        <div className="truncate text-xs text-muted-foreground">{label}</div>
        <div className="truncate text-sm font-medium text-foreground">{value}</div>
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
    <PillTabs
      items={values.map((value) => ({ key: String(value), label: format(value) }))}
      activeKey={current}
      onSelect={onPick}
      disabled={disabled}
    />
  );
}

export function ScheduleCard({ stats, onStatsChanged }: { stats: BackupStats | null; onStatsChanged: () => void }) {
  const { t, i18n } = useTranslation();
  const [isSavingSettings, setIsSavingSettings] = useState(false);
  const [enabled, setEnabled] = useState(false);
  const [intervalHours, setIntervalHours] = useState("24");
  const [maxFiles, setMaxFiles] = useState("14");
  const [saved, setSaved] = useState<BackupSettings | null>(null);
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
    setSaved(settings);
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
  const isIntervalTooHigh = Number(intervalHours) > MAX_INTERVAL_HOURS;
  const isMaxFilesTooHigh = Number(maxFiles) > MAX_FILES;
  const dirty =
    saved !== null &&
    (enabled !== saved.enabled ||
      intervalHours !== String(saved.interval_hours) ||
      maxFiles !== String(saved.max_files));
  const resetButton = canResetSettings && (
    <Button variant="glassDanger" isLoading={isResettingSettings} onClick={() => setIsResetConfirmOpen(true)}>
      {t("common.reset")}
    </Button>
  );

  return (
    <>
      <form onSubmit={(event) => void handleSaveSettings(event)} className="flex">
        <Section
          stretched
          className="flex-1"
          icon={Database}
          title={t("backups.schedule.title")}
          description={t("backups.schedule.description")}
          aside={
            saved !== null && (
              <StatusPill tone={saved.enabled ? "success" : "warning"}>
                {saved.enabled ? t("backups.schedule.badgeOn") : t("backups.schedule.badgeOff")}
              </StatusPill>
            )
          }
          footer={
            settingsState.kind === "ready" &&
            (canManageSettings ? (
              <SaveFooter dirty={dirty} saving={isSavingSettings} disabled={isIntervalTooHigh || isMaxFilesTooHigh} beside={resetButton} />
            ) : (
              resetButton && <div className="mt-4 flex items-center gap-3">{resetButton}</div>
            ))
          }
        >
          {settingsState.kind === "loading" && <Spinner size="card" />}
          {settingsState.kind === "error" && <ErrorState text={t("common.loadError")} />}
          {settingsState.kind === "ready" && (
            <>
              <SectionRows>
                <Row icon={Power} label={t("backups.schedule.enabledLabel")} hint={t("backups.schedule.enabledHint")}>
                  <Switch checked={enabled} onChange={setEnabled} disabled={!canManageSettings} />
                </Row>
              </SectionRows>

              <div className="mt-2 flex flex-1 flex-col gap-3">
                <div className={`flex flex-1 flex-col ${INNER_CARD_CLASS}`}>
                  <div className={`flex flex-wrap gap-3 transition-opacity ${dimmed}`}>
                    <div className="min-w-40 flex-1">
                      <Field
                        label={t("backups.schedule.intervalLabel")}
                        htmlFor="backups-interval"
                        info={t("backups.schedule.intervalHint")}
                        error={isIntervalTooHigh ? t("errors.validation.max", { max: MAX_INTERVAL_HOURS }) : null}
                      >
                        <div className="flex flex-col gap-1.5">
                          <Input
                            id="backups-interval"
                            type="number"
                            onKeyDown={blockNonIntegerKeys}
                            min={1}
                            step="1"
                            max={MAX_INTERVAL_HOURS}
                            aria-invalid={isIntervalTooHigh}
                            value={intervalHours}
                            onChange={(event) => setIntervalHours(event.target.value)}
                            disabled={!canManageSettings || !enabled}
                          />
                          {canManageSettings && (
                            <PresetButtons
                              values={INTERVAL_PRESETS}
                              current={intervalHours}
                              onPick={setIntervalHours}
                              format={String}
                              disabled={!enabled}
                            />
                          )}
                        </div>
                      </Field>
                    </div>
                    <div className="min-w-40 flex-1">
                      <Field
                        label={t("backups.schedule.maxFilesLabel")}
                        htmlFor="backups-max-files"
                        info={t("backups.schedule.maxFilesHint")}
                        error={isMaxFilesTooHigh ? t("errors.validation.max", { max: MAX_FILES }) : null}
                      >
                        <div className="flex flex-col gap-1.5">
                          <Input
                            id="backups-max-files"
                            type="number"
                            onKeyDown={blockNonIntegerKeys}
                            min={1}
                            step="1"
                            max={MAX_FILES}
                            aria-invalid={isMaxFilesTooHigh}
                            value={maxFiles}
                            onChange={(event) => setMaxFiles(event.target.value)}
                            disabled={!canManageSettings || !enabled}
                          />
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
                  </div>

                </div>

                {canViewStats && stats !== null && (
                  <div className={`flex flex-wrap items-center lg:h-[86px] ${INNER_CARD_CLASS}`}>
                    <TimelineItem
                      icon={Clock}
                      tone="bg-accent text-primary"
                      label={t("backups.schedule.nextRun")}
                      value={stats.next_run_at === null ? "—" : formatDateTime(stats.next_run_at, i18n.language)}
                      detail={
                        stats.next_run_at === null ? undefined : formatRelative(stats.next_run_at, i18n.language)
                      }
                    />
                    <div className="hidden w-px self-stretch bg-white/[0.08] sm:block" />
                    <TimelineItem
                      icon={ShieldCheck}
                      tone="bg-success/10 text-success"
                      label={t("backups.schedule.lastBackup")}
                      value={lastBackupAt === null ? "—" : formatDateTime(lastBackupAt, i18n.language)}
                      detail={lastBackupAt === null ? undefined : formatRelative(lastBackupAt, i18n.language)}
                    />
                  </div>
                )}
              </div>
            </>
          )}
        </Section>
      </form>

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
