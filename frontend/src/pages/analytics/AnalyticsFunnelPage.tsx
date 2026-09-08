import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { getFunnel } from "@entities/analytics/api";
import type { Funnel, AnalyticsPeriodDays, FunnelStep } from "@entities/analytics/api";
import { PeriodToggle } from "@shared/ui/PeriodToggle";
import { Spinner } from "@shared/ui/Spinner";

type FunnelState = { kind: "loading" } | { kind: "error" } | { kind: "ready"; data: Funnel };

function FunnelStepRow({ step }: { step: FunnelStep }) {
  const { t } = useTranslation();
  const pct = Math.min(100, step.pct_of_start * 100);
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium text-foreground">{t(`analytics.funnel.steps.${step.key}`)}</span>
        <span className="tabular-nums text-muted-foreground">
          {step.count.toLocaleString()}{" "}
          <span className="text-xs">
            ({(step.pct_of_start * 100).toFixed(1)}% {t("analytics.funnel.ofStart")})
          </span>
        </span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-white/[0.06]">
        <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-muted-foreground">
        {(step.pct_of_prev * 100).toFixed(1)}% {t("analytics.funnel.ofPrevious")}
      </span>
    </div>
  );
}

export function AnalyticsFunnelPage() {
  const { t } = useTranslation();
  const [days, setDays] = useState<AnalyticsPeriodDays>(7);
  const [state, setState] = useState<FunnelState>({ kind: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    setState({ kind: "loading" });
    getFunnel(days, controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setState({ kind: "ready", data });
      })
      .catch(() => {
        if (!controller.signal.aborted) setState({ kind: "error" });
      });
    return () => controller.abort();
  }, [days]);

  return (
    <div className="flex flex-col gap-4 pb-2">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-[13px] font-semibold text-foreground">{t("analytics.funnel.title")}</h2>
        <PeriodToggle value={days} onChange={setDays} />
      </div>

      {state.kind === "loading" && <Spinner className="py-12" />}
      {state.kind === "error" && (
        <div className="py-6 text-center text-sm text-error">{t("analytics.funnel.loadError")}</div>
      )}
      {state.kind === "ready" && (
        <div className="flex flex-col gap-5 rounded-2xl border border-border bg-surface/40 p-4">
          {state.data.steps.map((step) => (
            <FunnelStepRow key={step.key} step={step} />
          ))}
        </div>
      )}
    </div>
  );
}
