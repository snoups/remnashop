import { BarChart3, Loader2 } from "lucide-react";
import { useTranslation } from "react-i18next";

import { type AdLink, getAdLinkStats } from "@entities/advertising/api";
import { roiClassName } from "@entities/advertising/format";
import { formatMoney, formatPercent } from "@shared/lib/format";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { ErrorState } from "@shared/ui/EmptyState";
import { Tooltip } from "@shared/ui/Tooltip";
import { Card } from "@shared/ui/Card";
import { KpiTile } from "@shared/ui/KpiTile";
import { DAY_MS } from "@shared/lib/period";

const CHART_FALLBACK_DAYS = 30;

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
      <ErrorState text={t("advertising.stats.loadError")} />
    );
  }

  const stats = state.data;
  const rows = new Map(stats.daily_registrations.map((row) => [row.day, row]));
  const days = lastDays(periodDays || CHART_FALLBACK_DAYS).map((day) => ({
    day,
    count: rows.get(day)?.count ?? 0,
    byChannel: rows.get(day)?.by_channel ?? {},
  }));
  const peak = days.reduce((best, day) => (day.count > best.count ? day : best), days[0]);
  const formatDay = (day: string) =>
    new Date(`${day}T00:00:00Z`).toLocaleDateString(i18n.language, { day: "numeric", month: "short", timeZone: "UTC" });
  const formatLongDay = (day: string) =>
    new Date(`${day}T00:00:00Z`).toLocaleDateString(i18n.language, { day: "numeric", month: "long", timeZone: "UTC" });
  const none = t("common.none");

  return (
    <div className="flex flex-col gap-3">
      <div className="grid grid-cols-2 gap-3">
        <KpiTile
          label={t("advertising.stats.attributions")}
          value={String(stats.attributions_count)}
          hint={t("advertising.stats.channelSplit", {
            bot: stats.attributions_by_channel.BOT ?? 0,
            web: stats.attributions_by_channel.WEBCABINET ?? 0,
          })}
        />
        <KpiTile
          label={t("advertising.stats.paidCount")}
          value={String(stats.paid_count)}
          hint={`${t("advertising.stats.conversionRate")} ${
            stats.attributions_count > 0 ? formatPercent(stats.conversion_rate, i18n.language) : none
          }`}
        />
        <KpiTile
          label={t("advertising.stats.cost")}
          value={formatMoney(stats.cost, stats.report_currency, i18n.language)}
          hint={`${t("advertising.stats.cpa")} ${
            stats.cpa !== null ? formatMoney(stats.cpa, stats.report_currency, i18n.language) : none
          }`}
        />
        <KpiTile
          label={t("advertising.stats.revenue")}
          value={formatMoney(stats.revenue, stats.report_currency, i18n.language)}
          hint={
            <>
              {t("advertising.stats.roi")}{" "}
              <span className={`font-semibold ${roiClassName(stats.roi)}`}>
                {stats.roi !== null ? formatPercent(stats.roi, i18n.language, true) : none}
              </span>
            </>
          }
        />
      </div>

      <Card>
        <div className="flex items-baseline justify-between gap-2">
          <h3 className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-foreground">
            <BarChart3 className="size-3.5" />
            {t("advertising.stats.daily")}
          </h3>
          {peak.count > 0 && (
            <span className="text-[12px] tabular-nums text-muted-foreground">
              {t("advertising.stats.peak", { count: peak.count, day: formatDay(peak.day) })}
            </span>
          )}
        </div>
        <div className="mt-3 flex h-24 items-end gap-[3px]">
          {days.map((day, index) => {
            const split = t("advertising.stats.channelSplit", {
              bot: day.byChannel.BOT ?? 0,
              web: day.byChannel.WEBCABINET ?? 0,
            });
            const heading = `${formatLongDay(day.day)}: ${day.count}`;
            const edge = index / days.length;
            return (
              <div
                key={day.day}
                className="group relative flex h-full flex-1 items-end"
              >
                <div
                  className={`min-h-px w-full rounded-t-[3px] transition-colors group-hover:bg-primary ${
                    day.count > 0 && day.day === peak.day ? "bg-primary" : "bg-primary/35"
                  }`}
                  style={{ height: peak.count > 0 ? `${(day.count / peak.count) * 100}%` : "1px" }}
                />
                <Tooltip
                  text={day.count > 0 ? `${heading}\n${split}` : heading}
                  side={edge < 0.25 ? "top-start" : edge > 0.75 ? "top-end" : "top"}
                />
              </div>
            );
          })}
        </div>
        <div className="mt-1.5 flex justify-between text-[11px] text-muted-foreground">
          <span>{formatDay(days[0].day)}</span>
          <span>{formatDay(days[days.length - 1].day)}</span>
        </div>
      </Card>
    </div>
  );
}
