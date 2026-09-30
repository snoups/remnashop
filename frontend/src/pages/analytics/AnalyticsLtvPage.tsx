import { TrendingUp } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { getLtvDistribution } from "@entities/analytics/api";
import type { LtvDistribution } from "@entities/analytics/api";
import { CURRENCY_SYMBOL } from "@entities/payments/api";
import { AnalyticsCardHeader } from "@pages/analytics/AnalyticsCardHeader";
import { Card } from "@shared/ui/Card";
import { LIST_HEAD_CLASS } from "@shared/ui/classes";
import { EmptyState } from "@shared/ui/EmptyState";
import { Spinner } from "@shared/ui/Spinner";

type LtvState = { kind: "loading" } | { kind: "error" } | { kind: "ready"; data: LtvDistribution };

const BAR_AREA_HEIGHT_PX = 280;

export function AnalyticsLtvPage() {
  const { t } = useTranslation();
  const [state, setState] = useState<LtvState>({ kind: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    getLtvDistribution(controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setState({ kind: "ready", data });
      })
      .catch(() => {
        if (!controller.signal.aborted) setState({ kind: "error" });
      });
    return () => controller.abort();
  }, []);

  if (state.kind === "loading") return <Spinner size="page" />;
  if (state.kind === "error") {
    return <div className="py-6 text-center text-sm text-error">{t("analytics.ltv.loadError")}</div>;
  }

  const { buckets, report_currency: currency } = state.data;
  const symbol = CURRENCY_SYMBOL[currency] ?? currency;
  const total = buckets.reduce((sum, bucket) => sum + bucket.users, 0);
  const max = Math.max(1, ...buckets.map((bucket) => bucket.users));
  const header = (
    <AnalyticsCardHeader
      icon={TrendingUp}
      title={t("analytics.ltv.title")}
      description={`${t("analytics.ltv.titleHint")} (${currency})`}
    />
  );

  if (total === 0) {
    return (
      <Card>
        {header}
        <EmptyState text={t("analytics.ltv.empty")} size="page" />
      </Card>
    );
  }

  return (
    <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
      <Card>
        {header}
        <div
          className="mt-5 grid items-end gap-4 px-2"
          style={{ gridTemplateColumns: `repeat(${buckets.length}, minmax(0, 1fr))`, height: BAR_AREA_HEIGHT_PX + 28 }}
        >
          {buckets.map((bucket) => (
            <div key={bucket.label} className="flex flex-col gap-2">
              <span className="text-center text-[13px] font-bold tabular-nums text-foreground">{bucket.users}</span>
              <div
                className="rounded-t-[10px] rounded-b-sm bg-primary transition-all"
                style={{
                  height: Math.max(4, (bucket.users / max) * BAR_AREA_HEIGHT_PX),
                  opacity: 0.35 + (0.5 * bucket.users) / max,
                }}
              />
            </div>
          ))}
        </div>
        <div
          className="mx-2 grid gap-4 border-t border-border pt-2"
          style={{ gridTemplateColumns: `repeat(${buckets.length}, minmax(0, 1fr))` }}
        >
          {buckets.map((bucket) => (
            <span key={bucket.label} className="text-center text-[12px] tabular-nums text-muted-foreground">
              {bucket.label}
            </span>
          ))}
        </div>
      </Card>

      <Card variant="list">
        <div className={`${LIST_HEAD_CLASS} flex justify-between pt-2.5`}>
          <span>{t("analytics.ltv.rangeColumn")}</span>
          <span>{t("analytics.ltv.usersAxis")}</span>
        </div>
        {buckets.map((bucket, index) => (
          <div key={bucket.label} className="flex items-center gap-3 rounded-full px-3 py-2.5">
            <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-white/[0.06] text-[12px] font-bold text-foreground">
              Q{index + 1}
            </span>
            <span className="flex-1 text-[13px] font-medium tabular-nums text-foreground">
              {symbol} {bucket.label}
            </span>
            <span className="text-[13px] font-semibold tabular-nums text-foreground">{bucket.users}</span>
            <span className="w-10 text-right text-[12px] tabular-nums text-muted-foreground">
              {Math.round((bucket.users / total) * 100)}%
            </span>
          </div>
        ))}
      </Card>
    </div>
  );
}
