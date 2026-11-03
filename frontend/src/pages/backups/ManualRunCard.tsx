import { Archive, HardDrive, Play, TriangleAlert } from "lucide-react";
import { useState, type ComponentType } from "react";
import { useTranslation } from "react-i18next";

import { type BackupKind, type BackupRun, type BackupStats, createBackupRun } from "@entities/backups/api";
import { usePermissions } from "@entities/user/use-current-user";
import { BACKUP_KINDS, KIND_ICON } from "@pages/backups/kinds";
import { getErrorMessage } from "@shared/api/http";
import { formatBytes } from "@shared/lib/format";
import { toast } from "@shared/lib/toast";
import { Button } from "@shared/ui/Button";
import { GLASS_INNER_CARD_CLASS } from "@shared/ui/classes";
import { FieldHint } from "@shared/ui/FieldHint";
import { IconCircle } from "@shared/ui/glass/IconCircle";
import { Section } from "@shared/ui/glass/Section";
import { Pressable } from "@shared/ui/Pressable";

const INNER_CARD_CLASS = `gap-3 p-3.5 ${GLASS_INNER_CARD_CLASS}`;

function StatCard({
  icon,
  label,
  value,
  isAlert = false,
}: {
  icon: ComponentType<{ className?: string }>;
  label: string;
  value: string;
  isAlert?: boolean;
}) {
  return (
    <div className={`flex min-w-0 flex-col justify-between ${INNER_CARD_CLASS}`}>
      <IconCircle icon={icon} />
      <div className="min-w-0">
        <div className={`truncate text-[15px] font-semibold ${isAlert ? "text-error" : "text-foreground"}`}>{value}</div>
        <div className="truncate text-[12px] text-muted-foreground">{label}</div>
      </div>
    </div>
  );
}

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
    <Section stretched className="h-full" icon={Play} title={t("backups.manual.title")} description={t("backups.manual.description")}>
      <div className="mt-4 flex flex-1 flex-col gap-3">
        {canCreateRun && (
          <div className={`flex flex-1 flex-col ${INNER_CARD_CLASS}`}>
            <div className="grid gap-2 sm:grid-cols-2">
              {BACKUP_KINDS.map((kind) => {
                const isActive = runKind === kind;
                return (
                  <Pressable
                    key={kind}
                    type="button"
                    onClick={() => setRunKind(kind)}
                    className={`flex items-start gap-3 rounded-xl border p-3 text-left transition-colors ${
                      isActive
                        ? "border-primary/45 bg-primary/[0.07]"
                        : "border-white/[0.08] bg-white/[0.03] hover:bg-white/[0.06]"
                    }`}
                  >
                    <IconCircle icon={KIND_ICON[kind]} />
                    <div className="flex min-w-0 flex-col gap-0.5">
                      <span className="text-[13px] font-medium text-foreground">{t(`backups.kind.${kind}`)}</span>
                      <span className="text-[12px] text-muted-foreground">{t(`backups.kindDescription.${kind}`)}</span>
                    </div>
                  </Pressable>
                );
              })}
            </div>
            <div className="mt-auto flex items-center gap-2">
              <Button variant="glassAccent" onClick={() => void handleRunNow()} icon={Play} isLoading={isStartingRun}>
                {t("backups.manual.runNow")}
              </Button>
              <FieldHint text={t("backups.manual.runHint")} glass />
            </div>
          </div>
        )}

        {canViewStats && stats !== null && (
          // 138px = the schedule card's 86px timeline + its 52px footer, so the cards above match in height
          <div className="mt-auto grid grid-cols-3 gap-3 lg:h-[138px]">
            <StatCard icon={Archive} label={t("backups.manual.statCompleted")} value={String(stats.completed_count)} />
            <StatCard icon={HardDrive} label={t("backups.manual.statSize")} value={formatBytes(stats.total_size_bytes, i18n.language)} />
            <StatCard
              icon={TriangleAlert}
              label={t("backups.manual.statFailed")}
              value={String(stats.failed_count)}
              isAlert={stats.failed_count > 0}
            />
          </div>
        )}
      </div>
    </Section>
  );
}
