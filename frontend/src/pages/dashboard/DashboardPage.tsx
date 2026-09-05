import { AlertCircle, Bot, Loader2, ShieldCheck, Tag, Ticket } from "lucide-react";
import type { ComponentType } from "react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { listEventLog } from "@entities/event-log/api";
import type { EventLogEntry } from "@entities/event-log/api";
import { getOverview } from "@entities/overview/api";
import type { Overview, OverviewPeriodDays } from "@entities/overview/api";
import { getBotSettings } from "@entities/settings/api";
import type { BotSettings } from "@entities/settings/api";
import { useCurrentUser } from "@entities/user/use-current-user";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import type { Permission } from "@shared/types/rbac";

type OverviewState = { kind: "loading" } | { kind: "error" } | { kind: "ready"; data: Overview };

const PERIOD_OPTIONS: OverviewPeriodDays[] = [7, 30, 90];

export function fillDailySeries<T extends { day: string }>(
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

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-1 rounded-xl border border-border bg-white/[0.03] px-4 py-3">
      <span className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">{label}</span>
      <span className="text-xl font-bold text-foreground">{value}</span>
    </div>
  );
}

function PeriodToggle({
  value,
  onChange,
}: {
  value: OverviewPeriodDays;
  onChange: (days: OverviewPeriodDays) => void;
}) {
  const { t } = useTranslation();
  return (
    <div className="inline-flex rounded-full border border-border p-0.5">
      {PERIOD_OPTIONS.map((days) => (
        <button
          key={days}
          type="button"
          onClick={() => onChange(days)}
          className={`rounded-full px-3 py-1 text-[12px] font-semibold transition-colors ${
            value === days ? "bg-accent text-accent-foreground" : "text-muted-foreground hover:text-foreground"
          }`}
        >
          {t("dashboard.periodDays", { count: days })}
        </button>
      ))}
    </div>
  );
}

function TrendChart({
  title,
  data,
  color,
  valueFormatter,
}: {
  title: string;
  data: { day: string; value: number }[];
  color: string;
  valueFormatter: (value: number) => string;
}) {
  const gradientId = `overview-trend-${color.replace("#", "")}`;
  return (
    <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-4">
      <h3 className="mb-3 text-[13px] font-semibold text-foreground">{title}</h3>
      <ResponsiveContainer width="100%" height={200}>
        <AreaChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.25} />
              <stop offset="100%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#e8ecfb17" vertical={false} />
          <XAxis
            dataKey="day"
            tickFormatter={(value: string) => value.slice(5)}
            tick={{ fill: "#8b93b8", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis tick={{ fill: "#8b93b8", fontSize: 11 }} axisLine={false} tickLine={false} width={40} />
          <Tooltip
            formatter={(value) => valueFormatter(Number(value))}
            contentStyle={{ background: "#393c47", border: "1px solid #e8ecfb17", borderRadius: 12 }}
            labelStyle={{ color: "#e8ecfb" }}
            itemStyle={{ color: "#e8ecfb" }}
          />
          <Area type="monotone" dataKey="value" stroke={color} strokeWidth={2} fill={`url(#${gradientId})`} dot={false} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

function RecentEventsCard() {
  const { t } = useTranslation();
  const [state] = useAsyncResource((signal) => listEventLog({ pageSize: 8 }, signal));

  return (
    <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-4">
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
        <div className="flex items-center gap-2 py-6 text-error">
          <AlertCircle className="size-4" />
          <span className="text-sm">{t("dashboard.loadError")}</span>
        </div>
      )}
      {state.kind === "ready" && (
        <div className="flex flex-col divide-y divide-border/50">
          {state.data.items.length === 0 && (
            <p className="py-4 text-sm text-muted-foreground">{t("dashboard.noEvents")}</p>
          )}
          {state.data.items.map((entry: EventLogEntry) => (
            <div key={entry.id} className="flex items-center justify-between gap-3 py-2 text-sm">
              <span className="truncate text-foreground">{t(`eventLog.events.${entry.event_type}`)}</span>
              <span className="shrink-0 text-[11px] text-muted-foreground">
                {new Date(entry.occurred_at).toLocaleString()}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function BotStatusAndLinksCard({ permissions }: { permissions: Permission[] }) {
  const { t } = useTranslation();
  const showBotStatus = permissions.includes("BOT_SETTINGS_VIEW");
  const [botState] = useAsyncResource<BotSettings | null>((signal) =>
    showBotStatus ? getBotSettings(signal) : Promise.resolve(null),
  );

  const links: { to: string; label: string; icon: ComponentType<{ className?: string }> }[] = [];
  if (permissions.includes("PLANS_CREATE")) {
    links.push({ to: "/dashboard/plans", label: t("dashboard.quickLinks.createPlan"), icon: Tag });
  }
  if (permissions.includes("PROMOCODES_CREATE")) {
    links.push({ to: "/dashboard/promocodes", label: t("dashboard.quickLinks.createPromocode"), icon: Ticket });
  }
  if (permissions.includes("ADMINS_MANAGE")) {
    links.push({ to: "/dashboard/admins", label: t("dashboard.quickLinks.createAdmin"), icon: ShieldCheck });
  }

  if (!showBotStatus && links.length === 0) return null;

  return (
    <div className="flex flex-col gap-3 rounded-2xl border border-white/[0.08] bg-white/[0.03] p-4">
      {showBotStatus && (
        <div className="flex items-center gap-2.5">
          <Bot className="size-4 shrink-0 text-muted-foreground" />
          <span className="text-sm text-foreground">{t("dashboard.botStatus")}</span>
          {botState.kind === "ready" && botState.data && (
            <span
              className={`ml-auto shrink-0 rounded-full border px-2 py-0.5 text-[10.5px] font-semibold uppercase tracking-wide ${
                botState.data.is_configured
                  ? "border-success/30 bg-success/10 text-success"
                  : "border-border bg-white/[0.04] text-muted-foreground"
              }`}
            >
              {botState.data.is_configured ? t("dashboard.botConfigured") : t("dashboard.botNotConfigured")}
            </span>
          )}
        </div>
      )}
      {links.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {links.map(({ to, label, icon: Icon }) => (
            <Link
              key={to}
              to={to}
              className="flex items-center gap-1.5 rounded-full border border-border px-3.5 py-1.5 text-[12.5px] font-medium text-foreground/90 transition-colors hover:bg-white/5"
            >
              <Icon className="size-3.5" />
              {label}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

export function DashboardPage() {
  const { t } = useTranslation();
  const userState = useCurrentUser();
  const permissions = userState.kind === "ready" ? userState.data.effective_permissions : [];

  const [days, setDays] = useState<OverviewPeriodDays>(7);
  const [overviewState, setOverviewState] = useState<OverviewState>({ kind: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    setOverviewState({ kind: "loading" });
    getOverview(days, controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setOverviewState({ kind: "ready", data });
      })
      .catch(() => {
        if (!controller.signal.aborted) setOverviewState({ kind: "error" });
      });
    return () => controller.abort();
  }, [days]);

  if (overviewState.kind === "loading") {
    return (
      <div className="flex flex-1 items-center justify-center text-muted-foreground">
        <Loader2 className="size-6 animate-spin" />
      </div>
    );
  }
  if (overviewState.kind === "error") {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-2 text-error">
        <AlertCircle className="size-6" />
        <p className="text-sm">{t("dashboard.loadError")}</p>
      </div>
    );
  }

  const overview = overviewState.data;
  const revenueTotal = overview.payments
    ? Object.entries(overview.payments.revenue_by_currency)
        .map(([currency, amount]) => `${amount} ${currency}`)
        .join(", ") || "—"
    : "—";
  const revenueChartData = overview.payments
    ? fillDailySeries(overview.payments.daily_revenue, days, (day) => ({ day, amount: "0" })).map((d) => ({
        day: d.day,
        value: Number(d.amount),
      }))
    : [];
  const registrationChartData = overview.users
    ? fillDailySeries(overview.users.daily_registrations, days, (day) => ({ day, count: 0 })).map((d) => ({
        day: d.day,
        value: d.count,
      }))
    : [];

  return (
    <div className="flex flex-col gap-4 pb-2">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-bold text-foreground">{t("sidebar.overview")}</h1>
        <PeriodToggle value={days} onChange={setDays} />
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {overview.users && (
          <>
            <StatCard label={t("dashboard.stats.totalUsers")} value={String(overview.users.total)} />
            <StatCard label={t("dashboard.stats.newToday")} value={String(overview.users.new_today)} />
          </>
        )}
        {overview.subscriptions && (
          <StatCard
            label={t("dashboard.stats.activeSubscriptions")}
            value={String(overview.subscriptions.active)}
          />
        )}
        {overview.payments && (
          <>
            <StatCard label={t("dashboard.stats.paidOrders")} value={String(overview.payments.paid_orders_count)} />
            <StatCard label={t("dashboard.stats.revenue")} value={revenueTotal} />
          </>
        )}
      </div>

      {(overview.payments || overview.users) && (
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
          {overview.payments && (
            <TrendChart
              title={t("dashboard.charts.revenue")}
              data={revenueChartData}
              color="#00c758"
              valueFormatter={(v) => `${v.toFixed(2)} ${overview.payments?.report_currency ?? ""}`}
            />
          )}
          {overview.users && (
            <TrendChart
              title={t("dashboard.charts.registrations")}
              data={registrationChartData}
              color="#22d3ee"
              valueFormatter={(v) => String(v)}
            />
          )}
        </div>
      )}

      {userState.kind === "ready" && (
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
          {permissions.includes("EVENT_LOG_VIEW") && <RecentEventsCard />}
          <BotStatusAndLinksCard permissions={permissions} />
        </div>
      )}
    </div>
  );
}
