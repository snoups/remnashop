import type { ParseKeys } from "i18next";
import { ArrowDown, Filter } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { formatPercent } from "@shared/lib/format";
import { getFunnel } from "@entities/analytics/api";
import type { AnalyticsPeriodDays, FunnelStep } from "@entities/analytics/api";
import { Badge } from "@shared/ui/Badge";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { Card } from "@shared/ui/Card";
import { EYEBROW_CLASS } from "@shared/ui/classes";
import { ErrorState } from "@shared/ui/EmptyState";
import { KpiTile } from "@shared/ui/KpiTile";
import { PeriodPills } from "@shared/ui/PeriodPills";
import { Spinner } from "@shared/ui/Spinner";
import { CardHeader } from "@shared/ui/CardHeader";

function FunnelStepRow({ step, index }: { step: FunnelStep; index: number }) {
  const { t, i18n } = useTranslation();
  return (
    <div className="flex flex-col">
      {index > 0 && (
        <div className="flex items-center gap-2 py-0.5 pl-[26px] text-[11.5px] text-muted-foreground">
          <ArrowDown className="size-3" />
          <span className="tabular-nums text-foreground">{formatPercent(step.pct_of_prev, i18n.language)}</span>
          {t("analytics.funnel.ofPrevious")}
        </div>
      )}
      <div className="grid grid-cols-[32px_minmax(0,160px)_minmax(0,1fr)_72px_56px] items-center gap-3 rounded-full px-3 py-2.5">
        <span className="flex size-8 items-center justify-center rounded-full bg-white/[0.06] text-[13px] font-bold text-foreground">
          {index + 1}
        </span>
        <span className="truncate text-[13.5px] font-medium text-foreground">{t(`analytics.funnel.steps.${step.key}` as ParseKeys)}</span>
        <span className="h-2.5 overflow-hidden rounded-full bg-white/[0.06]">
          <span
            className="block h-full rounded-full bg-primary transition-all"
            style={{ width: `${Math.min(100, step.pct_of_start * 100)}%` }}
          />
        </span>
        <span className="text-right text-[15px] font-bold tabular-nums text-foreground">
          {step.count.toLocaleString(i18n.language)}
        </span>
        <span className="text-right text-[12.5px] tabular-nums text-muted-foreground">
          {formatPercent(step.pct_of_start, i18n.language)}
        </span>
      </div>
    </div>
  );
}

export function AnalyticsFunnelPage() {
  const { t, i18n } = useTranslation();
  const [days, setDays] = useState<AnalyticsPeriodDays>(7);
  const [state] = useAsyncResource((signal) => getFunnel(days, signal), { deps: [days] });

  const steps = state.kind === "ready" ? state.data.steps : [];
  const firstPaid = steps.find((step) => step.key === "first_paid");
  // the step losing the largest share of the one before it
  const biggestDrop =
    steps[0]?.count > 0
      ? steps.slice(1).reduce<{ step: FunnelStep; prev: FunnelStep } | null>((worst, step, i) => {
          return !worst || step.pct_of_prev < worst.step.pct_of_prev ? { step, prev: steps[i] } : worst;
        }, null)
      : null;

  return (
    <div className="flex flex-col gap-4 pb-2">
      <div className="flex justify-end">
        <PeriodPills value={days} onChange={setDays} />
      </div>

      {state.kind === "loading" && <Spinner size="page" />}
      {state.kind === "error" && (
        <ErrorState text={t("analytics.funnel.loadError")} />
      )}
      {state.kind === "ready" && (
        <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
          <Card>
            <CardHeader
              icon={Filter}
              title={t("analytics.funnel.title")}
              description={t("analytics.funnel.description")}
            />
            <div className="mt-2 flex flex-col">
              {steps.map((step, index) => (
                <FunnelStepRow key={step.key} step={step} index={index} />
              ))}
            </div>
          </Card>

          <div className="flex flex-col gap-4">
            {firstPaid && steps[0] && (
              <KpiTile
                label={t("analytics.funnel.conversion")}
                value={formatPercent(firstPaid.pct_of_start, i18n.language)}
                hint={t("analytics.kpi.conversionOf", { paid: firstPaid.count, total: steps[0].count })}
              />
            )}
            {biggestDrop && (
              <Card className="flex flex-col gap-2">
                <span className={EYEBROW_CLASS}>{t("analytics.funnel.biggestDrop")}</span>
                <span className="text-[15px] font-semibold text-foreground">
                  {t(`analytics.funnel.steps.${biggestDrop.prev.key}` as ParseKeys)} → {t(`analytics.funnel.steps.${biggestDrop.step.key}` as ParseKeys)}
                </span>
                <Badge tone="warning" className="self-start">
                  {t("analytics.funnel.dropBadge", { pct: formatPercent(1 - biggestDrop.step.pct_of_prev, i18n.language) })}
                </Badge>
              </Card>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
