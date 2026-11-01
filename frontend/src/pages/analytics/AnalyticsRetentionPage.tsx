import type { ParseKeys } from "i18next";
import { BarChart3, Clock, Hourglass, Layers, Package, RefreshCw, TrendingUp } from "lucide-react";
import { useTranslation } from "react-i18next";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { getCohorts, getRetention } from "@entities/analytics/api";
import type { Cohorts, Retention } from "@entities/analytics/api";
import { usePermissions } from "@entities/user/use-current-user";
import { useOpenEntity } from "@shared/lib/entity-dialogs";
import { formatMoney, formatPercent } from "@shared/lib/format";
import { initials } from "@shared/lib/initials";
import { DAY_MS } from "@shared/lib/period";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import type { AsyncState } from "@shared/lib/use-async-resource";
import { Badge } from "@shared/ui/Badge";
import { Card } from "@shared/ui/Card";
import { CardHeader } from "@shared/ui/CardHeader";
import { EYEBROW_CLASS, LIST_BODY_CLASS, LIST_HEAD_CLASS } from "@shared/ui/classes";
import { EmptyState, ErrorState } from "@shared/ui/EmptyState";
import { KpiTile } from "@shared/ui/KpiTile";
import { Spinner } from "@shared/ui/Spinner";
import { Tag } from "@shared/ui/Tag";
import { AnalyticsToolbar } from "@pages/analytics/AnalyticsToolbar";
import { BarRows, ColumnChart, CurrencyNote, Legend } from "@pages/analytics/charts";
import type { BarRow, Column } from "@pages/analytics/charts";
import { ListRow } from "@shared/ui/ListRow";

const MONTH_COLUMNS = 12;
// above this fill the cell is light enough to need dark text
const DARK_TEXT_FROM = 0.45;
const SOON_DAYS = 7;
const CURVE_COHORTS = 3;
const CURVE_MIN_MONTHS = 6;
const EXPIRING_GRID = "grid grid-cols-[36px_minmax(0,1.4fr)_minmax(0,1fr)_110px_120px_80px] items-center gap-3";

// theme tokens, not hex: --color-primary follows the dashboard's appearance settings
const CHART_TICK = { fill: "var(--color-muted-foreground)", fontSize: 11 };
const CHART_TOOLTIP_STYLE = {
  contentStyle: { background: "var(--color-surface)", border: "1px solid var(--color-border)", borderRadius: 12 },
  labelStyle: { color: "var(--color-foreground)" },
  itemStyle: { color: "var(--color-foreground)" },
};

function retentionCellStyle(value: number): { background: string; color?: string } {
  const alpha = Math.max(0.06, Math.min(0.85, value));
  return {
    // the admin-picked accent, not a fixed cyan; the legend above uses it too
    background: `color-mix(in srgb, var(--color-primary) ${Math.round(alpha * 100)}%, transparent)`,
    color: alpha > DARK_TEXT_FROM ? "var(--color-primary-foreground)" : undefined,
  };
}

export function AnalyticsRetentionPage() {
  const { t } = useTranslation();
  const canCohorts = usePermissions().includes("ANALYTICS_COHORTS_VIEW");
  const [state] = useAsyncResource((signal) => getRetention(signal));
  const [cohorts] = useAsyncResource((signal) => (canCohorts ? getCohorts(signal) : Promise.resolve(null)), {
    deps: [canCohorts],
  });

  return (
    <div className="flex flex-col gap-4 pb-2">
      <AnalyticsToolbar periodIndependent currency={state.kind === "ready" ? state.data.report_currency : undefined} />
      {state.kind === "loading" && <Spinner size="page" />}
      {state.kind === "error" && <ErrorState text={t("common.loadError")} />}
      {state.kind === "ready" && <Overview data={state.data} cohorts={cohorts} />}
    </div>
  );
}

function Overview({ data, cohorts }: { data: Retention; cohorts: AsyncState<Cohorts | null> }) {
  const { t, i18n } = useTranslation();
  const language = i18n.language;
  const currency = data.report_currency;
  const cohortData = cohorts.kind === "ready" ? cohorts.data : null;

  const activeTotal = data.active_by_plan.reduce((sum, plan) => sum + plan.active, 0);
  const planRows: BarRow[] = data.active_by_plan.map((plan) => ({
    key: plan.plan_name,
    label: plan.plan_name,
    value: plan.active,
    cells: [
      plan.active.toLocaleString(language),
      plan.limited > 0 ? <Badge key="limited" tone="warning">{t("analytics.retention.limited", { value: plan.limited.toLocaleString(language) })}</Badge> : "",
      formatPercent(activeTotal > 0 ? plan.active / activeTotal : 0, language),
    ],
  }));

  const monthFormat = new Intl.DateTimeFormat(language, { month: "short" });
  const churnColumns: Column[] = data.monthly_churn.map((row) => {
    const [year, month] = row.month.split("-").map(Number);
    return {
      key: row.month,
      label: monthFormat.format(new Date(year, month - 1, 1)),
      segments: [{ value: row.base > 0 ? row.rate * 100 : 0, className: "bg-warning" }],
      caption: row.base > 0 ? formatPercent(row.rate, language) : t("common.none"),
    };
  });

  return (
    <>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {data.points.map((point) => (
          <KpiTile
            key={point.months}
            icon={RefreshCw}
            label={t("analytics.retention.after", { count: point.months })}
            value={point.eligible > 0 ? formatPercent(point.rate, language) : t("common.none")}
            hint={point.eligible > 0 ? t("analytics.retention.afterCaption") : t("analytics.retention.noneEligible")}
          />
        ))}
        <KpiTile
          icon={Hourglass}
          label={t("analytics.retention.avgLifetime")}
          value={t("analytics.retention.monthsValue", {
            value: data.avg_paid_months.toLocaleString(language, { minimumFractionDigits: 1, maximumFractionDigits: 1 }),
          })}
          hint={t("analytics.retention.avgLifetimeCaption")}
        />
      </div>

      <ExpiringCard data={data} />

      <div className={`grid grid-cols-1 gap-4 ${cohortData ? "lg:grid-cols-2" : ""}`}>
        {cohortData && <CurveCard data={cohortData} />}
        <Card>
          <CardHeader
            icon={BarChart3}
            title={t("analytics.retention.churnTitle")}
            description={t("analytics.retention.churnDescription")}
          />
          <div className="pt-4">
            <ColumnChart columns={churnColumns} empty={t("analytics.empty")} />
          </div>
        </Card>
      </div>

      <Card>
        <CardHeader
          icon={Package}
          title={t("analytics.retention.byPlanTitle")}
          description={t("analytics.retention.byPlanDescription")}
        />
        <BarRows rows={planRows} empty={t("analytics.empty")} />
      </Card>

      {cohorts.kind === "error" && <ErrorState text={t("common.loadError")} />}
      {cohortData && <CohortHeatmap data={cohortData} />}

      <CurrencyNote currency={currency} />
    </>
  );
}

function ExpiringCard({ data }: { data: Retention }) {
  const { t, i18n } = useTranslation();
  const language = i18n.language;
  const { openUser } = useOpenEntity();
  const currency = data.report_currency;
  const weekMax = Math.max(0, ...data.expiring_weeks.map((week) => week.count));
  const now = Date.now();

  return (
    <Card>
      <CardHeader
        icon={Clock}
        title={t("analytics.retention.expiringTitle")}
        description={t("analytics.retention.expiringDescription")}
        aside={
          <>
            <Tag>{t("analytics.retention.expiringPaid", { value: data.expiring_paid.toLocaleString(language) })}</Tag>
            <Tag>{t("analytics.retention.expiringTrials", { value: data.expiring_trials.toLocaleString(language) })}</Tag>
          </>
        }
      />
      <div className="grid grid-cols-2 gap-3 px-1 pb-4 pt-4 sm:grid-cols-4">
        {data.expiring_weeks.map((week) => (
          <div key={week.key} className="flex min-w-0 flex-col gap-1.5">
            <div className="flex items-baseline justify-between gap-2">
              <span className={EYEBROW_CLASS}>{t(`analytics.retention.weeks.${week.key}` as ParseKeys)}</span>
              <span className="text-[18px] font-bold tabular-nums text-foreground">{week.count.toLocaleString(language)}</span>
            </div>
            <div className="h-2.5 overflow-hidden rounded-full bg-white/[0.06]">
              <div className="h-full rounded-full bg-warning" style={{ width: `${weekMax > 0 ? (week.count / weekMax) * 100 : 0}%` }} />
            </div>
            <span className="text-[12px] tabular-nums text-muted-foreground">
              {t("analytics.retention.mrrAtRisk", { money: formatMoney(week.mrr_at_risk, currency, language) })}
            </span>
          </div>
        ))}
      </div>

      {data.expiring_top.length === 0 ? (
        <p className="py-6 text-center text-[13px] text-muted-foreground">{t("analytics.retention.expiringEmpty")}</p>
      ) : (
        <div className="overflow-x-auto">
          <div className="min-w-[640px]">
            <div className={`${EXPIRING_GRID} ${LIST_HEAD_CLASS}`}>
              <span />
              <span>{t("analytics.retention.customer")}</span>
              <span>{t("analytics.retention.plan")}</span>
              <span>{t("analytics.retention.expires")}</span>
              <span className="text-right">{t("analytics.totalPaid")}</span>
              <span className="text-right">{t("analytics.retention.renewals")}</span>
            </div>
            <div className={LIST_BODY_CLASS}>
              {data.expiring_top.map((row) => {
                const days = Math.max(1, Math.floor((Date.parse(row.expire_at) - now) / DAY_MS));
                const inDays = t("analytics.retention.inDays", { count: days });
                return (
                  <ListRow
                    key={row.user_id}
                    type="button"
                    onClick={() => openUser(row.user_id)}
                    className={EXPIRING_GRID}
                  >
                    <span className="flex size-9 items-center justify-center rounded-full bg-accent text-[12px] font-bold text-primary">
                      {initials(row.name)}
                    </span>
                    <span className="min-w-0">
                      <span className="block truncate text-[13px] font-medium text-foreground">{row.name}</span>
                      {row.username && (
                        <span className="block truncate font-mono text-[12px] text-muted-foreground">@{row.username}</span>
                      )}
                    </span>
                    <span className="truncate text-[13px] text-foreground">{row.plan_name}</span>
                    <span>{days <= SOON_DAYS ? <Badge tone="warning">{inDays}</Badge> : <Tag>{inDays}</Tag>}</span>
                    <span className="text-right text-[13px] font-semibold tabular-nums text-foreground">
                      {formatMoney(row.spent, currency, language)}
                    </span>
                    <span className="text-right text-[12.5px] tabular-nums text-muted-foreground">
                      {row.renewals.toLocaleString(language)}
                    </span>
                  </ListRow>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </Card>
  );
}

function CurveCard({ data }: { data: Cohorts }) {
  const { t, i18n } = useTranslation();
  const language = i18n.language;
  const rows = data.items.filter((row) => row.cohort_size > 0);
  const recent = rows.filter((row) => row.retention_by_month.length >= CURVE_MIN_MONTHS).slice(-CURVE_COHORTS).reverse();
  const length = Math.min(MONTH_COLUMNS, Math.max(0, ...rows.map((row) => row.retention_by_month.length)));

  const points = Array.from({ length }, (_, month) => {
    const values = rows.flatMap((row) => (month < row.retention_by_month.length ? [row.retention_by_month[month]] : []));
    const point: Record<string, number | string | undefined> = {
      month: `M${month}`,
      average: values.reduce((sum, value) => sum + value, 0) / values.length,
    };
    for (const row of recent) point[row.cohort] = row.retention_by_month[month];
    return point;
  });

  return (
    <Card>
      <CardHeader
        icon={TrendingUp}
        title={t("analytics.retention.curveTitle")}
        description={t("analytics.retention.curveDescription")}
      />
      {points.length === 0 ? (
        <p className="py-6 text-center text-[13px] text-muted-foreground">{t("analytics.empty")}</p>
      ) : (
        <div className="flex flex-col gap-3 pt-4">
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={points} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
              <XAxis dataKey="month" tick={CHART_TICK} axisLine={false} tickLine={false} />
              <YAxis
                domain={[0, 1]}
                ticks={[0, 0.5, 1]}
                tickFormatter={(value: number) => formatPercent(value, language)}
                tick={CHART_TICK}
                axisLine={false}
                tickLine={false}
                width={40}
              />
              <Tooltip formatter={(value) => formatPercent(Number(value), language)} {...CHART_TOOLTIP_STYLE} />
              {recent.map((row) => (
                <Line
                  key={row.cohort}
                  type="monotone"
                  name={row.cohort}
                  dataKey={row.cohort}
                  stroke="var(--color-muted-foreground)"
                  strokeWidth={1.5}
                  dot={false}
                />
              ))}
              <Line
                type="monotone"
                name={t("analytics.retention.average")}
                dataKey="average"
                stroke="var(--color-primary)"
                strokeWidth={2.5}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
          <Legend
            items={[
              { className: "bg-primary", label: t("analytics.retention.average") },
              ...(recent.length > 0
                ? [{ className: "bg-muted-foreground", label: recent.map((row) => row.cohort).join(", ") }]
                : []),
            ]}
          />
        </div>
      )}
    </Card>
  );
}

function CohortHeatmap({ data }: { data: Cohorts }) {
  const { t, i18n } = useTranslation();
  const language = i18n.language;

  return (
    <Card>
      <CardHeader
        icon={Layers}
        title={t("analytics.retention.cohortsTitle")}
        description={t("analytics.retention.cohortsDescription")}
        aside={
          <div className="flex items-center gap-2 text-[12px] text-muted-foreground">
            {formatPercent(0, language)}
            <span className="h-2 w-28 rounded-full bg-gradient-to-r from-primary/5 to-primary/85" />
            {formatPercent(1, language)}
          </div>
        }
      />

      {data.items.every((row) => row.cohort_size === 0) ? (
        <EmptyState text={t("analytics.empty")} size="page" />
      ) : (
        <div className="-mx-1 mt-3 overflow-x-auto">
          <table className="w-full border-separate border-spacing-1 text-[12px] tabular-nums">
            <thead>
              <tr className={EYEBROW_CLASS}>
                <th className="px-1 pb-1.5 text-left font-semibold">{t("analytics.retention.cohortColumn")}</th>
                <th className="px-1.5 pb-1.5 text-right font-semibold">{t("analytics.retention.sizeColumn")}</th>
                {Array.from({ length: MONTH_COLUMNS }).map((_, idx) => (
                  <th key={idx} className="min-w-11 pb-1.5 text-center font-semibold">
                    M{idx}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.items.map((row) => (
                <tr key={row.cohort}>
                  <td className="px-1 font-mono text-[12px] text-foreground">{row.cohort}</td>
                  <td className="px-1.5 text-right text-[12.5px] font-semibold text-foreground">{row.cohort_size.toLocaleString(language)}</td>
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
                        {formatPercent(value, language)}
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
