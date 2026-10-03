import type { ParseKeys, TFunction } from "i18next";
import { AlertCircle, Cpu, Loader2, Users } from "lucide-react";
import { useId, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { listEventLog } from "@entities/event-log/api";
import type { EventLogEntry } from "@entities/event-log/api";
import { getOnlineChart, getOverview, getRegistrationsChart, getRevenueChart } from "@entities/overview/api";
import type {
  HostMemory,
  OverviewGranularity,
  OverviewPeriodDays,
  OverviewSubscriptions,
  RuntimeProcess,
} from "@entities/overview/api";
import { useCurrentUser, usePermissions } from "@entities/user/use-current-user";
import { formatBytes, formatMoney } from "@shared/lib/format";
import { useAsyncResource, type AsyncState } from "@shared/lib/use-async-resource";
import { useRefreshSignal } from "@shared/lib/refresh-signal";
import { ErrorState } from "@shared/ui/EmptyState";
import { PeriodPills } from "@shared/ui/PeriodPills";
import { KpiTile } from "@shared/ui/KpiTile";
import { LIST_BODY_CLASS } from "@shared/ui/classes";
import { formatDateTime } from "@shared/lib/relative-time";

// each chart card owns its period: refetches on its own pill switch or a global refresh
function useChart<T>(
  fetchChart: (days: OverviewPeriodDays, signal: AbortSignal) => Promise<T>,
  days: OverviewPeriodDays,
  refreshKey: number,
): AsyncState<T> {
  const [state] = useAsyncResource((signal) => fetchChart(days, signal), { deps: [fetchChart, days, refreshKey] });
  return state;
}

function fillDailySeries<T extends { day: string }>(
  sparse: T[],
  days: number,
  emptyValue: (day: string) => T,
): T[] {
  const byDay = new Map(sparse.map((item) => [item.day, item]));
  const result: T[] = [];
  const today = new Date();
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(today);
    d.setUTCDate(d.getUTCDate() - i);
    const key = d.toISOString().slice(0, 10);
    result.push(byDay.get(key) ?? emptyValue(key));
  }
  return result;
}

// theme tokens, not hex: --color-primary follows the dashboard's appearance settings
const CHART_TICK = { fill: "var(--color-muted-foreground)", fontSize: 11 };
const CHART_TOOLTIP_STYLE = {
  contentStyle: { background: "var(--color-surface)", border: "1px solid var(--color-border)", borderRadius: 12 },
  labelStyle: { color: "var(--color-foreground)" },
  itemStyle: { color: "var(--color-foreground)" },
};

function TrendChart({
  title,
  total,
  badges,
  days,
  onDaysChange,
  data,
  color,
  valueFormatter,
  granularity,
  valueName,
}: {
  title: string;
  total?: string;
  badges?: string[];
  days: OverviewPeriodDays;
  onDaysChange: (days: OverviewPeriodDays) => void;
  data: { day: string; value: number }[];
  color: string;
  valueFormatter: (value: number) => string;
  granularity: OverviewGranularity;
  valueName?: string;
}) {
  const gradientId = useId();
  return (
    <div className="rounded-2xl border border-border bg-surface/40 p-4">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <h3 className="text-[13px] font-semibold text-foreground">{title}</h3>
          {total && <p className="mt-1 text-2xl font-bold text-foreground">{total}</p>}
        </div>
        <div className="flex shrink-0 flex-col items-end gap-2">
          <PeriodPills value={days} onChange={onDaysChange} />
          {badges && badges.length > 0 && (
            <div className="flex gap-1.5">
              {badges.map((badge) => (
                <span
                  key={badge}
                  className="rounded-full border border-border bg-white/[0.04] px-2.5 py-1 text-[11px] text-muted-foreground"
                >
                  {badge}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
      <ResponsiveContainer width="100%" height={200}>
        <AreaChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.25} />
              <stop offset="100%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
          <XAxis
            dataKey="day"
            tickFormatter={(value: string) => (granularity === "month" ? value.slice(0, 7) : value.slice(5))}
            tick={CHART_TICK}
            axisLine={false}
            tickLine={false}
          />
          <YAxis tick={CHART_TICK} axisLine={false} tickLine={false} width={40} />
          <Tooltip
            formatter={(value) => valueFormatter(Number(value))}
            {...CHART_TOOLTIP_STYLE}
          />
          <Area type="monotone" name={valueName ?? title} dataKey="value" stroke={color} strokeWidth={2} fill={`url(#${gradientId})`} dot={false} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

function RecentEventsCard({ refreshKey }: { refreshKey: number }) {
  const { t, i18n } = useTranslation();
  const [state] = useAsyncResource((signal) => listEventLog({ pageSize: 8 }, signal), {
    deps: [refreshKey],
    keepData: true,
  });

  return (
    <div className="rounded-2xl border border-border bg-surface/40 p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-[13px] font-semibold text-foreground">{t("dashboard.recentEvents")}</h3>
        <Link to="/dashboard/event-log" className="text-[12px] font-semibold text-primary hover:text-primary-hover">
          {t("dashboard.viewAllEvents")}
        </Link>
      </div>
      {state.kind === "loading" && (
        <div className="flex justify-center py-6 text-muted-foreground">
          <Loader2 className="size-5 animate-spin" />
        </div>
      )}
      {state.kind === "error" && (
        <ErrorState text={t("dashboard.loadError")} />
      )}
      {state.kind === "ready" && (
        <div className={`${LIST_BODY_CLASS}`}>
          {state.data.items.length === 0 && (
            <p className="py-4 text-sm text-muted-foreground">{t("dashboard.noEvents")}</p>
          )}
          {state.data.items.map((entry: EventLogEntry) => (
            <div key={entry.id} className="flex items-center justify-between gap-3 py-2 text-sm">
              <span className="truncate text-foreground">{t(`eventLog.events.${entry.event_type}` as ParseKeys)}</span>
              <span className="shrink-0 text-[11px] text-muted-foreground">
                {formatDateTime(entry.occurred_at, i18n.language)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ChartCardMessage({ kind }: { kind: "loading" | "error" }) {
  const { t } = useTranslation();
  return (
    <div className="flex min-h-[268px] flex-col items-center justify-center gap-2 rounded-2xl border border-border bg-surface/40 p-4">
      {kind === "loading" ? (
        <Loader2 className="size-5 animate-spin text-muted-foreground" />
      ) : (
        <>
          <AlertCircle className="size-5 text-error" />
          <span className="text-sm text-error">{t("dashboard.loadError")}</span>
        </>
      )}
    </div>
  );
}

function RevenueCard({ refreshKey }: { refreshKey: number }) {
  const { t, i18n } = useTranslation();
  const [days, setDays] = useState<OverviewPeriodDays>(7);
  const state = useChart(getRevenueChart, days, refreshKey);

  if (state.kind !== "ready") return <ChartCardMessage kind={state.kind} />;
  const transactions = state.data;

  const revenueTotal =
    Object.entries(transactions.revenue_by_currency)
      .map(([currency, amount]) => formatMoney(amount, currency, i18n.language))
      .join(", ") || "—";
  const revenueSeries =
    days === 0
      ? transactions.daily
      : fillDailySeries(transactions.daily, days, (day) => ({ day, amount: "0" }));
  const revenueChartData = revenueSeries.map((d) => ({ day: d.day, value: Number(d.amount) }));

  return (
    <TrendChart
      title={t("dashboard.charts.revenue")}
      total={revenueTotal}
      badges={Object.keys(transactions.revenue_by_currency)}
      days={days}
      onDaysChange={setDays}
      data={revenueChartData}
      color="var(--color-success)"
      valueFormatter={(v) => formatMoney(v, transactions.report_currency, i18n.language, true)}
      granularity={state.data.granularity}
    />
  );
}

function RegistrationsCard({ refreshKey }: { refreshKey: number }) {
  const { t } = useTranslation();
  const [days, setDays] = useState<OverviewPeriodDays>(7);
  const state = useChart(getRegistrationsChart, days, refreshKey);

  if (state.kind !== "ready") return <ChartCardMessage kind={state.kind} />;
  const registrationSeries =
    days === 0
      ? state.data.daily
      : fillDailySeries(state.data.daily, days, (day) => ({ day, count: 0 }));
  const registrationChartData = registrationSeries.map((d) => ({ day: d.day, value: d.count }));
  const registrationsTotal = registrationChartData.reduce((sum, d) => sum + d.value, 0);

  return (
    <TrendChart
      title={t("dashboard.charts.registrations")}
      total={registrationsTotal > 0 ? `+${registrationsTotal}` : "—"}
      days={days}
      onDaysChange={setDays}
      data={registrationChartData}
      color="var(--color-primary)"
      valueFormatter={(v) => String(v)}
      granularity={state.data.granularity}
    />
  );
}

function OnlineCard({ refreshKey }: { refreshKey: number }) {
  const { t } = useTranslation();
  const [days, setDays] = useState<OverviewPeriodDays>(7);
  const state = useChart(getOnlineChart, days, refreshKey);

  if (state.kind !== "ready") return <ChartCardMessage kind={state.kind} />;
  const online = state.data;

  const peakSeries =
    days === 0 ? online.daily_peak : fillDailySeries(online.daily_peak, days, (day) => ({ day, count: 0 }));
  const peakChartData = peakSeries.map((d) => ({ day: d.day, value: d.count }));

  return (
    <TrendChart
      title={t("dashboard.charts.online")}
      total={online.current > 0 ? String(online.current) : "—"}
      days={days}
      onDaysChange={setDays}
      data={peakChartData}
      color="#818cf8"
      valueFormatter={(v) => String(v)}
      granularity={state.data.granularity}
      valueName={t("dashboard.charts.onlineValue")}
    />
  );
}

const SUBSCRIPTION_SLICE_COLORS = {
  active: "var(--color-primary)",
  limited: "var(--color-warning)",
  expired: "var(--color-muted-foreground)",
} as const;

function SubscriptionsDonut({ subscriptions }: { subscriptions: OverviewSubscriptions }) {
  const { t } = useTranslation();
  const slices = [
    { key: "active", label: t("dashboard.subscriptions.active"), value: subscriptions.active },
    { key: "limited", label: t("dashboard.subscriptions.limited"), value: subscriptions.limited },
    { key: "expired", label: t("dashboard.subscriptions.expired"), value: subscriptions.expired },
  ] as const;

  return (
    <div className="rounded-2xl border border-border bg-surface/40 p-4">
      <h3 className="mb-3 text-[13px] font-semibold text-foreground">
        {t("dashboard.charts.subscriptions")}
      </h3>
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
        <div className="relative mx-auto size-[160px] shrink-0">
          {subscriptions.total > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={slices.map((s) => ({ label: s.label, value: s.value }))}
                  dataKey="value"
                  nameKey="label"
                  innerRadius={52}
                  outerRadius={78}
                  paddingAngle={2}
                  stroke="none"
                >
                  {slices.map((s) => (
                    <Cell key={s.key} fill={SUBSCRIPTION_SLICE_COLORS[s.key]} />
                  ))}
                </Pie>
                <Tooltip
                  {...CHART_TOOLTIP_STYLE}
                />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="size-full rounded-full border-[26px] border-white/[0.06]" />
          )}
          <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-2xl font-bold text-foreground">{subscriptions.total}</span>
          </div>
        </div>
        <div className="flex flex-1 flex-col gap-2">
          {slices.map((s) => (
            <div key={s.key} className="flex items-center justify-between gap-3 text-[13px]">
              <span className="flex items-center gap-2 text-muted-foreground">
                <span
                  className="size-2.5 rounded-full"
                  style={{ background: SUBSCRIPTION_SLICE_COLORS[s.key] }}
                />
                {s.label}
              </span>
              <span className="font-semibold text-foreground">{s.value}</span>
            </div>
          ))}
          <div className="mt-1 flex flex-col gap-1.5 border-t border-border/50 pt-2">
            <div className="flex items-center justify-between gap-3 text-[13px]">
              <span className="text-muted-foreground">{t("dashboard.subscriptions.expiringSoon")}</span>
              <span className="font-semibold text-warning">{subscriptions.expiring_soon}</span>
            </div>
            <div className="flex items-center justify-between gap-3 text-[13px]">
              <span className="text-muted-foreground">{t("dashboard.subscriptions.disabled")}</span>
              <span className="font-semibold text-foreground">{subscriptions.disabled}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function formatUptime(t: TFunction, seconds: number): string {
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (days > 0) {
    const daysLabel = t("dashboard.runtime.durationDays", { count: days });
    return hours > 0 ? `${daysLabel} ${t("dashboard.runtime.durationHours", { count: hours })}` : daysLabel;
  }
  if (hours > 0) {
    const hoursLabel = t("dashboard.runtime.durationHours", { count: hours });
    return minutes > 0
      ? `${hoursLabel} ${t("dashboard.runtime.durationMinutes", { count: minutes })}`
      : hoursLabel;
  }
  return t("dashboard.runtime.durationMinutes", { count: minutes });
}

// process names are docker-entrypoint.sh's targets, identifiers left untranslated
const RUNTIME_PROCESS_LABELS: Record<string, string> = {
  api: "API",
  telegram: "Telegram bot",
  worker: "Worker",
  scheduler: "Scheduler",
};

function RuntimeProcessCard({ process }: { process: RuntimeProcess }) {
  const { t, i18n } = useTranslation();
  return (
    <div className="flex flex-col gap-2 rounded-2xl border border-border bg-surface/40 p-4">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <div className="flex size-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Cpu className="size-4" />
          </div>
          <span className="text-[13px] font-semibold text-foreground">
            {RUNTIME_PROCESS_LABELS[process.process] ?? process.process}
          </span>
        </div>
        <span className="text-[11px] text-muted-foreground">PID {process.pid}</span>
      </div>
      <div className="flex items-center justify-between text-[12px]">
        <span className="text-muted-foreground">{t("dashboard.runtime.memory")}</span>
        <span className="font-semibold text-foreground">{formatBytes(process.rss_bytes, i18n.language)}</span>
      </div>
      <div className="flex items-center justify-between text-[12px]">
        <span className="text-muted-foreground">{t("dashboard.runtime.uptime")}</span>
        <span className="font-semibold text-foreground">
          {formatUptime(t, process.uptime_seconds)}
        </span>
      </div>
      <div className="mt-1 flex flex-col gap-1.5 rounded-xl border border-border/50 bg-white/[0.03] p-2.5">
        <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
          {t("dashboard.runtime.eventLoop")}
        </span>
        <div className="flex items-center justify-between text-[12px]">
          <span className="text-muted-foreground">{t("dashboard.runtime.eventLoopDelay")}</span>
          <span className="font-semibold text-foreground">
            {process.event_loop_delay_ms.toFixed(2)} {t("dashboard.runtime.units.millisecond")}
          </span>
        </div>
        <div className="flex items-center justify-between text-[12px]">
          <span className="text-muted-foreground">{t("dashboard.runtime.eventLoopP99")}</span>
          <span className="font-semibold text-foreground">
            {process.event_loop_p99_ms.toFixed(2)} {t("dashboard.runtime.units.millisecond")}
          </span>
        </div>
      </div>
    </div>
  );
}

function HostMemoryCard({ memory }: { memory: HostMemory }) {
  const { t, i18n } = useTranslation();
  const percent =
    memory.total_bytes > 0 ? Math.min(100, (memory.used_bytes / memory.total_bytes) * 100) : 0;
  return (
    <div className="rounded-2xl border border-border bg-surface/40 p-4">
      <div className="mb-2 flex items-center justify-between gap-3">
        <span className="text-[13px] font-semibold text-foreground">
          {t("dashboard.runtime.ramUsage")}
        </span>
        <span className="text-[12px] text-muted-foreground">
          {t("dashboard.runtime.totalRam")}: {formatBytes(memory.total_bytes, i18n.language)}
        </span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-white/[0.06]">
        <div
          className="h-full rounded-full bg-primary transition-all"
          style={{ width: `${percent}%` }}
        />
      </div>
      <div className="mt-1.5 text-[11px] text-muted-foreground">
        {formatBytes(memory.used_bytes, i18n.language)} ({percent.toFixed(0)}%)
      </div>
    </div>
  );
}

function SystemStatusSection({
  runtime,
  memory,
}: {
  runtime: RuntimeProcess[];
  memory: HostMemory | null;
}) {
  const { t } = useTranslation();
  if (runtime.length === 0 && !memory) return null;
  return (
    <div className="flex flex-col gap-3 rounded-2xl border border-border bg-surface/40 p-4">
      <h3 className="text-[13px] font-semibold text-foreground">{t("dashboard.runtime.title")}</h3>
      {runtime.length > 0 && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {runtime.map((process) => (
            <RuntimeProcessCard key={process.process} process={process} />
          ))}
        </div>
      )}
      {memory && <HostMemoryCard memory={memory} />}
    </div>
  );
}

export function DashboardPage() {
  const { t } = useTranslation();
  const userState = useCurrentUser();
  const permissions = usePermissions();

  const { token: refreshKey } = useRefreshSignal();
  const [kpiState] = useAsyncResource(getOverview, { deps: [refreshKey], keepData: true });

  return (
    <div className="flex flex-col gap-4 pb-2">
      {kpiState.kind === "loading" && (
        <div className="flex justify-center py-4 text-muted-foreground">
          <Loader2 className="size-5 animate-spin" />
        </div>
      )}
      {kpiState.kind === "error" && (
        <ErrorState text={t("dashboard.loadError")} />
      )}
      {kpiState.kind === "ready" && kpiState.data.users && (
        <KpiTile
          icon={Users}
          label={t("dashboard.stats.totalUsers")}
          value={String(kpiState.data.users.total)}
        />
      )}

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        {kpiState.kind === "ready" && kpiState.data.subscriptions && (
          <SubscriptionsDonut subscriptions={kpiState.data.subscriptions} />
        )}
        <OnlineCard refreshKey={refreshKey} />
      </div>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        {permissions.includes("TRANSACTIONS_VIEW") && <RevenueCard refreshKey={refreshKey} />}
        {permissions.includes("USERS_VIEW") && <RegistrationsCard refreshKey={refreshKey} />}
      </div>

      {kpiState.kind === "ready" && (
        <SystemStatusSection runtime={kpiState.data.runtime} memory={kpiState.data.host_memory} />
      )}

      {userState.kind === "ready" && permissions.includes("EVENT_LOG_VIEW") && (
        <RecentEventsCard refreshKey={refreshKey} />
      )}
    </div>
  );
}
