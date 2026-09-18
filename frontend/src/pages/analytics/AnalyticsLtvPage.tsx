import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { getLtvDistribution } from "@entities/analytics/api";
import type { LtvDistribution } from "@entities/analytics/api";
import { FieldHint } from "@shared/ui/FieldHint";
import { Spinner } from "@shared/ui/Spinner";

type LtvState = { kind: "loading" } | { kind: "error" } | { kind: "ready"; data: LtvDistribution };

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

  const chartData = state.kind === "ready" ? state.data.buckets.map((b) => ({ label: b.label, users: b.users })) : [];
  const isEmpty = state.kind === "ready" && chartData.every((b) => b.users === 0);

  return (
    <div className="flex flex-col gap-4 pb-2">
      <h2 className="flex items-center gap-1.5 text-[13px] font-semibold text-foreground">
        {t("analytics.ltv.title")}
        {state.kind === "ready" && (
          <span className="font-normal text-muted-foreground">({state.data.report_currency})</span>
        )}
        <FieldHint text={t("analytics.ltv.titleHint")} side="bottom" />
      </h2>

      {state.kind === "loading" && <Spinner className="py-12" />}
      {state.kind === "error" && (
        <div className="py-6 text-center text-sm text-error">{t("analytics.ltv.loadError")}</div>
      )}
      {state.kind === "ready" && (
        <div className="rounded-2xl border border-border bg-surface/40 p-4">
          {isEmpty ? (
            <p className="py-6 text-center text-sm text-muted-foreground">{t("analytics.ltv.empty")}</p>
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <AreaChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e8ecfb17" vertical={false} />
                <XAxis dataKey="label" tick={{ fill: "#8b93b8", fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis
                  tick={{ fill: "#8b93b8", fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                  width={40}
                  allowDecimals={false}
                />
                <Tooltip
                  formatter={(value) => [String(value), t("analytics.ltv.usersAxis")]}
                  contentStyle={{ background: "#393c47", border: "1px solid #e8ecfb17", borderRadius: 12 }}
                  labelStyle={{ color: "#e8ecfb" }}
                  itemStyle={{ color: "#e8ecfb" }}
                />
                <Area
                  type="monotone"
                  dataKey="users"
                  name={t("analytics.ltv.usersAxis")}
                  stroke="#10b981"
                  strokeWidth={2}
                  fill="#10b981"
                  fillOpacity={0.3}
                  dot={false}
                />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>
      )}
    </div>
  );
}
