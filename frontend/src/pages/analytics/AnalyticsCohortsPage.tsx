import { Layers } from "lucide-react";
import { useTranslation } from "react-i18next";

import { getCohorts } from "@entities/analytics/api";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { Card } from "@shared/ui/Card";
import { EYEBROW_CLASS } from "@shared/ui/classes";
import { EmptyState, ErrorState } from "@shared/ui/EmptyState";
import { Spinner } from "@shared/ui/Spinner";
import { CardHeader } from "@shared/ui/CardHeader";

const MONTH_COLUMNS = 12;
// above this fill the cell is light enough to need dark text
const DARK_TEXT_FROM = 0.45;

function retentionCellStyle(value: number): { background: string; color?: string } {
  const alpha = Math.max(0.06, Math.min(0.85, value));
  return {
    // the admin-picked accent, not a fixed cyan; the legend above uses it too
    background: `color-mix(in srgb, var(--color-primary) ${Math.round(alpha * 100)}%, transparent)`,
    color: alpha > DARK_TEXT_FROM ? "var(--color-primary-foreground)" : undefined,
  };
}

export function AnalyticsCohortsPage() {
  const { t } = useTranslation();
  const [state] = useAsyncResource((signal) => getCohorts(signal));

  if (state.kind === "loading") return <Spinner size="page" />;
  if (state.kind === "error") {
    return <ErrorState text={t("analytics.cohorts.loadError")} />;
  }

  return (
    <Card>
      <CardHeader
        icon={Layers}
        title={t("analytics.cohorts.title")}
        description={t("analytics.cohorts.titleHint")}
        aside={
          <div className="flex items-center gap-2 text-[11.5px] text-muted-foreground">
            0%
            <span className="h-2 w-28 rounded-full bg-gradient-to-r from-primary/5 to-primary/85" />
            100%
          </div>
        }
      />

      {state.data.cohorts.every((row) => row.cohort_size === 0) ? (
        <EmptyState text={t("analytics.cohorts.empty")} size="page" />
      ) : (
        <div className="-mx-1 mt-3 overflow-x-auto">
          <table className="w-full border-separate border-spacing-1 text-[11.5px] tabular-nums">
            <thead>
              <tr className={EYEBROW_CLASS}>
                <th className="px-1 pb-1.5 text-left font-semibold">{t("analytics.cohorts.cohortColumn")}</th>
                <th className="px-1.5 pb-1.5 text-right font-semibold">{t("analytics.cohorts.sizeColumn")}</th>
                {Array.from({ length: MONTH_COLUMNS }).map((_, idx) => (
                  <th key={idx} className="min-w-11 pb-1.5 text-center font-semibold">
                    M{idx}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {state.data.cohorts.map((row) => (
                <tr key={row.cohort}>
                  <td className="px-1 font-mono text-[12px] text-foreground">{row.cohort}</td>
                  <td className="px-1.5 text-right text-[12.5px] font-semibold text-foreground">{row.cohort_size}</td>
                  {Array.from({ length: MONTH_COLUMNS }).map((_, idx) => {
                    const value = row.retention_by_month[idx];
                    return value === undefined ? (
                      <td key={idx} />
                    ) : (
                      <td
                        key={idx}
                        className="h-[30px] rounded-lg text-center text-foreground"
                        style={retentionCellStyle(value)}
                      >
                        {(value * 100).toFixed(0)}%
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
