import { Loader2, Play } from "lucide-react";
import { motion } from "motion/react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { type BackupKind, type BackupRun, type BackupStats, createBackupRun } from "@entities/backups/api";
import { usePermissions } from "@entities/user/use-current-user";
import { BACKUP_KINDS, KIND_ICON } from "@pages/backups/kinds";
import { getErrorMessage } from "@shared/api/http";
import { bounceTap } from "@shared/lib/bounceState";
import { formatBytes } from "@shared/lib/format";
import { toast } from "@shared/lib/toast";
import { Button } from "@shared/ui/Button";
import { Card } from "@shared/ui/Card";
import { CardHeader } from "@shared/ui/CardHeader";
import { EYEBROW_CLASS } from "@shared/ui/classes";
import { FieldHint } from "@shared/ui/FieldHint";

export function ManualRunCard({ stats, onRunStarted }: { stats: BackupStats | null; onRunStarted: (run: BackupRun) => void }) {
  const { t, i18n } = useTranslation();
  const [runKind, setRunKind] = useState<BackupKind>("DATABASE");
  const [isStartingRun, setIsStartingRun] = useState(false);

  const permissions = usePermissions();
  const canCreateRun = permissions.includes("BACKUPS_RUN_CREATE");
  const canViewStats = permissions.includes("BACKUPS_STATS_VIEW");

  const handleRunNow = async () => {
    setIsStartingRun(true);
    try {
      const run = await createBackupRun(runKind);
      toast.success(t("backups.manual.runStarted"));
      onRunStarted(run);
    } catch (err) {
      toast.error(getErrorMessage(err, t("backups.manual.runError")));
    } finally {
      setIsStartingRun(false);
    }
  };

  return (
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
              className="grid gap-2.5 sm:grid-cols-2"
            >
              {BACKUP_KINDS.map((kind) => {
                const Icon = KIND_ICON[kind];
                const isActive = runKind === kind;
                return (
                  <motion.button
                    key={kind}
                    type="button"
                    {...bounceTap()}
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
                  {formatBytes(stats.total_size_bytes, i18n.language)}
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
  );
}
