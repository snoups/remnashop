import { AlertCircle, Loader2 } from "lucide-react";
import { useTranslation } from "react-i18next";

import { type AdLink, type AdLinkChannel, getAdLinkStats } from "@entities/advertising/api";
import { formatMoney, formatPercent, roiClassName } from "@entities/advertising/format";
import { useAsyncResource } from "@shared/lib/use-async-resource";

const CHART_FALLBACK_DAYS = 30;
const DAY_MS = 86_400_000;
const CHANNELS: { channel: AdLinkChannel; dot: string }[] = [
  { channel: "BOT", dot: "bg-primary" },
  { channel: "WEBCABINET", dot: "bg-violet-400" },
];

interface AdLinkStatsPanelProps {
  adLink: AdLink;
  // 0 = all time; the chart then shows the last CHART_FALLBACK_DAYS days
  periodDays: number;
  createdFrom?: string;
}

function lastDays(count: number): string[] {
  const today = Date.UTC(new Date().getUTCFullYear(), new Date().getUTCMonth(), new Date().getUTCDate());
  return Array.from({ length: count }, (_, i) => new Date(today - (count - 1 - i) * DAY_MS).toISOString().slice(0, 10));
}

const cardClassName = "rounded-2xl border border-white/[0.07] bg-white/[0.02] p-3.5";
const labelClassName = "text-[11px] font-semibold uppercase tracking-wide text-muted-foreground";

export function AdLinkStatsPanel({ adLink, periodDays, createdFrom }: AdLinkStatsPanelProps) {
  const { t, i18n } = useTranslation();
  const [state] = useAsyncResource((signal) => getAdLinkStats(adLink.id, createdFrom, signal));

  if (state.kind === "loading") {
    return (
      <div className="flex justify-center py-6 text-muted-foreground">
        <Loader2 className="size-4 animate-spin" />
      </div>
    );
  }
  if (state.kind === "error") {
    return (
      <div className="flex items-center justify-center gap-2 py-6 text-sm text-error">
        <AlertCircle className="size-4" />
        {t("advertising.stats.loadError")}
      </div>
    );
  }

  const stats = state.data;
  const counts = new Map(stats.daily_registrations.map((row) => [row.day, row.count]));
  const days = lastDays(periodDays || CHART_FALLBACK_DAYS).map((day) => ({ day, count: counts.get(day) ?? 0 }));
  const peak = days.reduce((best, day) => (day.count > best.count ? day : best), days[0]);
  const formatDay = (day: string) =>
    new Date(`${day}T00:00:00Z`).toLocaleDateString(i18n.language, { day: "numeric", month: "short", timeZone: "UTC" });
  const none = t("advertising.stats.none");

  return (
    <div className="grid gap-3 md:grid-cols-[1.6fr_1fr_1fr]">
      <div className={cardClassName}>
        <div className="flex items-baseline justify-between gap-2">
          <span className={labelClassName}>{t("advertising.stats.daily")}</span>
          {peak.count > 0 && (
            <span className="text-[12px] tabular-nums text-muted-foreground">
              {t("advertising.stats.peak", { count: peak.count, day: formatDay(peak.day) })}
            </span>
          )}
        </div>
        <div className="mt-3 flex h-20 items-end gap-[3px]">
          {days.map((day) => (
            <div
              key={day.day}
              className={`min-h-px flex-1 rounded-t-[3px] ${
                day.count > 0 && day.day === peak.day ? "bg-primary" : "bg-primary/35"
              }`}
              style={{ height: peak.count > 0 ? `${(day.count / peak.count) * 100}%` : "1px" }}
            />
          ))}
        </div>
        <div className="mt-1.5 flex justify-between text-[11px] text-muted-foreground">
          <span>{formatDay(days[0].day)}</span>
          <span>{formatDay(days[days.length - 1].day)}</span>
        </div>
      </div>

      <div className={`${cardClassName} flex flex-col gap-3`}>
        <span className={labelClassName}>{t("advertising.stats.channels")}</span>
        <div className="flex h-2 gap-0.5 overflow-hidden rounded-full bg-white/[0.06]">
          {CHANNELS.map(({ channel, dot }) => {
            const count = stats.attributions_by_channel[channel] ?? 0;
            return count > 0 ? (
              <div key={channel} className={dot} style={{ width: `${(count / stats.attributions_count) * 100}%` }} />
            ) : null;
          })}
        </div>
        <div className="flex flex-col gap-2 text-[13px]">
          {CHANNELS.map(({ channel, dot }) => {
            const count = stats.attributions_by_channel[channel] ?? 0;
            return (
              <div key={channel} className="flex items-center gap-2">
                <span className={`size-2 rounded-full ${dot}`} />
                <span className="flex-1 text-foreground">{t(`advertising.channel.${channel}`)}</span>
                <span className="font-semibold tabular-nums text-foreground">{count}</span>
                <span className="w-10 text-right tabular-nums text-muted-foreground">
                  {stats.attributions_count > 0
                    ? formatPercent(String(count / stats.attributions_count), i18n.language)
                    : none}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      <div className={`${cardClassName} grid grid-cols-2 content-start gap-x-2.5 gap-y-3`}>
        <span className={`${labelClassName} col-span-2`}>{t("advertising.stats.economics")}</span>
        <Metric label={t("advertising.stats.revenue")} value={formatMoney(stats.revenue, stats.report_currency, i18n.language)} />
        <Metric label={t("advertising.stats.cost")} value={formatMoney(stats.cost, stats.report_currency, i18n.language)} />
        <Metric
          label={t("advertising.stats.cpa")}
          value={stats.cpa !== null ? formatMoney(stats.cpa, stats.report_currency, i18n.language) : none}
        />
        <Metric
          label={t("advertising.stats.roi")}
          value={stats.roi !== null ? formatPercent(stats.roi, i18n.language, true) : none}
          className={roiClassName(stats.roi)}
        />
      </div>
    </div>
  );
}

function Metric({ label, value, className = "text-foreground" }: { label: string; value: string; className?: string }) {
  return (
    <div>
      <div className="text-[11.5px] text-muted-foreground">{label}</div>
      <div className={`text-[15px] font-semibold tabular-nums ${className}`}>{value}</div>
    </div>
  );
}
