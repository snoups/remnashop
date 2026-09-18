import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { getCohorts } from "@entities/analytics/api";
import type { Cohorts } from "@entities/analytics/api";
import { FieldHint } from "@shared/ui/FieldHint";
import { Spinner } from "@shared/ui/Spinner";

type CohortsState = { kind: "loading" } | { kind: "error" } | { kind: "ready"; data: Cohorts };

const MONTH_COLUMNS = 12;

function retentionCellStyle(value: number | undefined): { background?: string; color?: string } {
  if (value === undefined) return {};
  const intensity = Math.min(0.85, value);
  return {
    background: `rgba(34, 211, 238, ${intensity})`,
    color: intensity > 0.4 ? "white" : undefined,
  };
}

export function AnalyticsCohortsPage() {
  const { t } = useTranslation();
  const [state, setState] = useState<CohortsState>({ kind: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    getCohorts(controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setState({ kind: "ready", data });
      })
      .catch(() => {
        if (!controller.signal.aborted) setState({ kind: "error" });
      });
    return () => controller.abort();
  }, []);

  return (
    <div className="flex flex-col gap-4 pb-2">
      <h2 className="flex items-center gap-1.5 text-[13px] font-semibold text-foreground">
        {t("analytics.cohorts.title")}
        <FieldHint text={t("analytics.cohorts.titleHint")} side="bottom" />
      </h2>

      {state.kind === "loading" && <Spinner className="py-12" />}
      {state.kind === "error" && (
        <div className="py-6 text-center text-sm text-error">{t("analytics.cohorts.loadError")}</div>
      )}
      {state.kind === "ready" && (
        <div className="overflow-x-auto rounded-2xl border border-border bg-surface/40 p-4">
          {state.data.cohorts.every((row) => row.cohort_size === 0) ? (
            <p className="py-6 text-center text-sm text-muted-foreground">{t("analytics.cohorts.empty")}</p>
          ) : (
            <table className="w-full text-xs">
              <thead className="border-b border-border text-muted-foreground">
                <tr>
                  <th className="px-2 py-2 text-left">{t("analytics.cohorts.cohortColumn")}</th>
                  <th className="px-2 py-2 text-right">{t("analytics.cohorts.sizeColumn")}</th>
                  {Array.from({ length: MONTH_COLUMNS }).map((_, idx) => (
                    <th key={idx} className="px-2 py-2 text-center">
                      M{idx}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {state.data.cohorts.map((row) => (
                  <tr key={row.cohort} className="border-b border-border/50 last:border-0">
                    <td className="px-2 py-2 font-mono text-foreground">{row.cohort}</td>
                    <td className="px-2 py-2 text-right tabular-nums text-foreground">{row.cohort_size}</td>
                    {Array.from({ length: MONTH_COLUMNS }).map((_, idx) => {
                      const value = row.retention_by_month[idx];
                      return (
                        <td key={idx} className="px-2 py-2 text-center tabular-nums" style={retentionCellStyle(value)}>
                          {value === undefined ? "—" : `${(value * 100).toFixed(0)}%`}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}
