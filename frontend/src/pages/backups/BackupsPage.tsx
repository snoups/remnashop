import { getBackupStats } from "@entities/backups/api";
import { usePermissions } from "@entities/user/use-current-user";
import { ManualRunCard } from "@pages/backups/ManualRunCard";
import { RunsCard } from "@pages/backups/RunsCard";
import { ScheduleCard } from "@pages/backups/ScheduleCard";
import { useBackupRuns } from "@pages/backups/use-backup-runs";
import { useAsyncResource } from "@shared/lib/use-async-resource";

export function BackupsPage() {
  const permissions = usePermissions();
  const canCreateRun = permissions.includes("BACKUPS_RUN_CREATE");
  const canViewRuns = permissions.includes("BACKUPS_RUN_VIEW");
  const canViewStats = permissions.includes("BACKUPS_STATS_VIEW");

  // stats are decorative; the rest of the page stays usable without them
  const [statsState, loadStats] = useAsyncResource((signal) =>
    canViewStats ? getBackupStats(signal) : Promise.resolve(null),
  );
  const stats = statsState.kind === "ready" ? statsState.data : null;

  const runs = useBackupRuns(canViewRuns, loadStats);

  return (
    <div className="flex flex-col gap-4">
      <div className="grid gap-4 lg:grid-cols-2">
        <ScheduleCard stats={stats} onStatsChanged={loadStats} />
        {(canCreateRun || canViewStats) && <ManualRunCard stats={stats} onRunStarted={runs.prepend} />}
      </div>
      {canViewRuns && <RunsCard runs={runs} onStatsChanged={loadStats} />}
    </div>
  );
}
