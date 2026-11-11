import type { ParseKeys } from "i18next";
import { BarChart3, Clock, Hourglass, Layers, Package, RefreshCw, TrendingUp, User } from "lucide-react";
import { useTranslation } from "react-i18next";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { getCohorts, getRetention, listExpiringCustomers } from "@entities/analytics/api";
import type { Cohorts, Retention } from "@entities/analytics/api";
import { usePermissions } from "@entities/user/use-current-user";
import { useOpenEntity } from "@shared/lib/entity-dialogs";
import { formatMoney, formatPercent } from "@shared/lib/format";
import { initials } from "@shared/lib/initials";
import { DAY_MS } from "@shared/lib/period";
import { LoadGateHold } from "@shared/lib/load-gate";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { usePaginatedList } from "@shared/lib/use-paginated-list";
import type { AsyncState } from "@shared/lib/use-async-resource";
import { Badge } from "@shared/ui/Badge";
import { CHART_CURSOR, ChartTooltip, MIN_CHART_POINTS, useChartAnimation, useChartEntered } from "@shared/ui/chart";
import { Section } from "@shared/ui/glass/Section";
import { EYEBROW_CLASS, GLASS_LIST_HEAD_CLASS, LIST_BODY_CLASS, STAT_VALUE_CLASS } from "@shared/ui/classes";
import { EmptyState, ErrorState } from "@shared/ui/glass/EmptyState";
import { KpiTile } from "@shared/ui/KpiTile";
import { LoadMoreButton } from "@shared/ui/LoadMoreButton";
import { Spinner } from "@shared/ui/Spinner";
import { Tag } from "@shared/ui/Tag";
import { BarRows, ColumnChart, Legend } from "@pages/analytics/charts";
import type { BarRow, Column } from "@pages/analytics/charts";
import { ListRow } from "@shared/ui/ListRow";

const MONTH_COLUMNS = 12;
// above this fill the cell is light enough to need dark text
const DARK_TEXT_FROM = 0.45;
const SOON_DAYS = 7;
const CURVE_COHORTS = 3;
const CURVE_MIN_MONTHS = 6;
const EXPIRING_GRID = "grid grid-cols-[32px_minmax(0,1.4fr)_minmax(0,1fr)_110px_120px_80px] items-center gap-3";

// theme tokens, not hex: --color-primary follows the dashboard's appearance settings
const CHART_TICK = { fill: "var(--color-muted-foreground)", fontSize: 12 };

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
    <div className="flex flex-col gap-5">
      <LoadGateHold isLoading={state.kind === "loading" || cohorts.kind === "loading"} />
      {state.kind === "loading" && <Spinner size="page" />}
      {state.kind === "error" && <ErrorState text={t("common.loadError")} size="page" />}
      {state.kind === "ready" && <Overview data={state.data} cohorts={cohorts} />}
    </div>
  );
}

function Overview({ data, cohorts }: { data: Retention; cohorts: AsyncState<Cohorts | null> }) {
  const { t, i18n } = useTranslation();
  const language = i18n.language;
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
      <div className="grid grid-cols-2 gap-5 xl:grid-cols-4">
        {data.points.map((point) => (
          <KpiTile
            panel
            key={point.months}
            icon={RefreshCw}
            label={t("analytics.retention.after", { count: point.months })}
            value={point.eligible > 0 ? formatPercent(point.rate, language) : t("common.none")}
            hint={point.eligible > 0 ? t("analytics.retention.afterCaption") : undefined}
          />
        ))}
        <KpiTile
          panel
          icon={Hourglass}
          label={t("analytics.retention.avgLifetime")}
          // 0 only while nobody has paid yet
          value={
            data.avg_paid_months > 0
              ? t("analytics.retention.monthsValue", {
                  value: data.avg_paid_months.toLocaleString(language, { minimumFractionDigits: 1, maximumFractionDigits: 1 }),
                })
              : t("common.none")
          }
          hint={t("analytics.retention.avgLifetimeCaption")}
        />
      </div>

      <ExpiringCard data={data} />

      <div className={`grid grid-cols-1 gap-5 ${cohortData ? "lg:grid-cols-2" : ""}`}>
        {cohortData && <CurveCard data={cohortData} />}
        <Section
          stretched
          icon={BarChart3}
          title={t("analytics.retention.churnTitle")}
          description={t("analytics.retention.churnDescription")}
        >
          <div className="px-3.5 pt-4">
            <ColumnChart
              columns={churnColumns}
              // no bars with subscribers to lose is no data; with them, a real 0%
              empty={data.monthly_churn.some((row) => row.base > 0) ? t("analytics.retention.noChurn") : t("analytics.empty")}
            />
          </div>
        </Section>
      </div>

      <Section
        icon={Package}
        title={t("analytics.retention.byPlanTitle")}
        description={t("analytics.retention.byPlanDescription")}
      >
        <BarRows rows={planRows} empty={t("analytics.empty")} />
      </Section>

      {cohorts.kind === "error" && <ErrorState text={t("common.loadError")} size="page" />}
      {cohortData && <CohortHeatmap data={cohortData} />}

    </>
  );
}

function ExpiringCard({ data }: { data: Retention }) {
  const { t, i18n } = useTranslation();
  const language = i18n.language;
  const canList = usePermissions().includes("ANALYTICS_EXPIRING_VIEW");
  const currency = data.report_currency;
  const weekMax = Math.max(0, ...data.expiring_weeks.map((week) => week.count));

  return (
    <Section
      icon={Clock}
      title={t("analytics.retention.expiringTitle")}
      description={t("analytics.retention.expiringDescription")}
      aside={
        <>
          <Tag>{t("analytics.retention.expiringPaid", { value: data.expiring_paid.toLocaleString(language) })}</Tag>
          <Tag>{t("analytics.retention.expiringTrials", { value: data.expiring_trials.toLocaleString(language) })}</Tag>
        </>
      }
    >
      <div className="grid grid-cols-2 gap-3 px-3.5 pb-6 pt-4 sm:grid-cols-4">
        {data.expiring_weeks.map((week) => (
          <div key={week.key} className="flex min-w-0 flex-col gap-1.5">
            <div className="flex items-baseline justify-between gap-2">
              <span className={EYEBROW_CLASS}>{t(`analytics.retention.weeks.${week.key}` as ParseKeys)}</span>
              <span className={`text-foreground ${STAT_VALUE_CLASS}`}>{week.count.toLocaleString(language)}</span>
            </div>
            <div className="h-2.5 overflow-hidden rounded-full glass-track">
              <div className="h-full rounded-full bg-warning transition-[width] duration-200 ease-out" style={{ width: `${weekMax > 0 ? (week.count / weekMax) * 100 : 0}%` }} />
            </div>
            <span className="text-xs tabular-nums text-muted-foreground">
              {t("analytics.retention.mrrAtRisk", { money: formatMoney(week.mrr_at_risk, currency, language) })}
            </span>
          </div>
        ))}
      </div>

      {canList && <ExpiringList currency={currency} />}
    </Section>
  );
}

function CurveCard({ data }: { data: Cohorts }) {
  const { t, i18n } = useTranslation();
  const language = i18n.language;
  const animation = useChartAnimation();
  const entered = useChartEntered();
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
    <Section
      stretched
      icon={TrendingUp}
      title={t("analytics.retention.curveTitle")}
      description={t("analytics.retention.curveDescription")}
    >
      {points.length < MIN_CHART_POINTS ? (
        <EmptyState text={points.length === 0 ? t("analytics.empty") : t("common.notEnoughData")} />
      ) : (
        <div className="flex flex-col gap-3 px-3.5 pt-4">
          {/* mounts as the page fades in, so the lines draw where they can be seen */}
          {!entered ? <div className="h-[220px]" /> : (
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
              <Tooltip
                cursor={CHART_CURSOR}
                content={({ active, payload, label }) =>
                  active && payload && payload.length > 0 ? (
                    <ChartTooltip
                      title={String(label)}
                      rows={payload.map((item) => ({
                        label: String(item.name),
                        value: formatPercent(Number(item.value), language),
                      }))}
                    />
                  ) : null
                }
              />
              {recent.map((row) => (
                <Line
                  key={row.cohort}
                  type="monotone"
                  name={row.cohort}
                  dataKey={row.cohort}
                  stroke="var(--color-muted-foreground)"
                  strokeWidth={1.5}
                  dot={false}
                  {...animation}
                />
              ))}
              <Line
                type="monotone"
                name={t("analytics.retention.average")}
                dataKey="average"
                stroke="var(--color-primary)"
                strokeWidth={2.5}
                dot={false}
                {...animation}
              />
            </LineChart>
          </ResponsiveContainer>
          )}
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
    </Section>
  );
}

function CohortHeatmap({ data }: { data: Cohorts }) {
  const { t, i18n } = useTranslation();
  const language = i18n.language;

  return (
    <Section
      icon={Layers}
      title={t("analytics.retention.cohortsTitle")}
      description={t("analytics.retention.cohortsDescription")}
      aside={
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          {formatPercent(0, language)}
          <span className="h-2 w-28 rounded-full bg-gradient-to-r from-primary/5 to-primary/85" />
          {formatPercent(1, language)}
        </div>
      }
    >

      {data.items.every((row) => row.cohort_size === 0) ? (
        <EmptyState text={t("analytics.empty")} size="page" />
      ) : (
        <div className="mx-2.5 mt-4 overflow-x-auto">
          <table className="w-full border-separate border-spacing-1 text-xs tabular-nums">
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
                  <td className="px-1 font-mono text-xs text-foreground">{row.cohort}</td>
                  <td className="px-1.5 text-right text-xs font-semibold text-foreground">{row.cohort_size.toLocaleString(language)}</td>
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
    </Section>
  );
}

const EXPIRING_PAGE_SIZE = 10;

function ExpiringList({ currency }: { currency: Retention["report_currency"] }) {
  const { t, i18n } = useTranslation();
  const language = i18n.language;
  const { openUser } = useOpenEntity();
  const { state, isLoadingMore, hasMore, loadMore } = usePaginatedList(
    (_: null, page, signal) => listExpiringCustomers(page, EXPIRING_PAGE_SIZE, signal),
    null,
    (row) => row.user_id,
  );
  const now = Date.now();

  if (state.kind === "loading") return <Spinner size="card" />;
  if (state.kind === "error") return <ErrorState text={t("common.loadError")} />;
  if (state.items.length === 0) return <EmptyState text={t("analytics.retention.expiringEmpty")} />;
  return (
    <div>
      <div className="overflow-x-auto">
        <div className="min-w-[640px]">
          <div className={`${EXPIRING_GRID} ${GLASS_LIST_HEAD_CLASS}`}>
            <span className="col-span-2">{t("analytics.retention.customer")}</span>
            <span>{t("analytics.retention.subscriptionsColumn")}</span>
            <span>{t("analytics.retention.expires")}</span>
            <span className="text-right">{t("analytics.totalPaid")}</span>
            <span className="text-right">{t("analytics.retention.renewals")}</span>
          </div>
          <div className={LIST_BODY_CLASS}>
            {state.items.map((row) => {
              const days = Math.max(1, Math.floor((Date.parse(row.expire_at) - now) / DAY_MS));
              const inDays = t("analytics.retention.inDays", { count: days });
              return (
                <ListRow
                  key={row.user_id}
                  type="button"
                  onClick={() => openUser(row.user_id)}
                  className={EXPIRING_GRID}
                >
                  <span className="flex size-8 items-center justify-center rounded-full bg-white/[0.06] text-xs font-bold text-foreground">
                    {row.name ? initials(row.name) : <User className="size-4" />}
                  </span>
                  <span className="min-w-0">
                    <span className="flex min-w-0 items-center gap-2">
                      <span className="truncate text-sm font-medium text-foreground">
                        {row.name || t("users.unnamed")}
                      </span>
                      <span className="shrink-0 font-mono text-xs text-muted-foreground">#{row.user_id}</span>
                    </span>
                    {row.username && (
                      <span className="block truncate font-mono text-xs text-muted-foreground">@{row.username}</span>
                    )}
                  </span>
                  <span className="flex min-w-0 items-center gap-1.5 text-sm text-foreground">
                    <span className="truncate">{row.plan_names[0]}</span>
                    {row.plan_names.length > 1 && <Tag>+{row.plan_names.length - 1}</Tag>}
                  </span>
                  <span>
                    <Badge tone={days <= SOON_DAYS ? "warning" : "neutral"}>
                      {inDays}
                    </Badge>
                  </span>
                  <span className="text-right text-sm font-semibold tabular-nums text-foreground">
                    {formatMoney(row.spent, currency, language)}
                  </span>
                  <span className="text-right text-xs tabular-nums text-muted-foreground">
                    {row.renewals.toLocaleString(language)}
                  </span>
                </ListRow>
              );
            })}
          </div>
        </div>
      </div>
      {hasMore && (
        <div className="px-2.5 py-1">
          <LoadMoreButton
            onClick={() => void loadMore()}
            isLoading={isLoadingMore}
            shown={state.items.length}
            total={state.total}
          />
        </div>
      )}
    </div>
  );
}
