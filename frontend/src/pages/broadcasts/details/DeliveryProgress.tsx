import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { RECALL_WINDOW_MS } from "@entities/broadcasts/api";
import type { Broadcast } from "@entities/broadcasts/api";
import { canRecall, processedCount } from "@entities/broadcasts/display";
import { formatDateTime } from "@shared/lib/relative-time";

const MS_PER_SECOND = 1000;
const SECONDS_PER_MINUTE = 60;

interface DeliveryProgressProps {
  broadcast: Broadcast;
  now: number;
  /** under a line at the bottom: the broadcast's parameters */
  children?: ReactNode;
}

// the bar's segments, in its order; the rest of the track is the queue
const SEGMENT_CLASS = {
  delivered: "bg-success",
  blocked: "bg-warning",
  failed: "bg-error",
  recalled: "bg-violet-400",
  canceled: "bg-muted-foreground",
  queued: "bg-white/20",
} as const;

export function DeliveryProgress({ broadcast: b, now, children }: DeliveryProgressProps) {
  const { t, i18n } = useTranslation();
  const processed = processedCount(b);
  const share = (n: number) => (b.total_count > 0 ? `${(n / b.total_count) * 100}%` : "0%");
  // not processed yet: queued while it runs, canceled once it's over (stopped, or a customer blocked mid-send)
  const unsent = Math.max(b.total_count - processed, 0);
  const finished = b.status === "COMPLETED" || b.status === "CANCELED" || b.status === "FAILED";
  const segments: { key: keyof typeof SEGMENT_CLASS; count: number }[] = [
    { key: "delivered", count: b.sent_count },
    { key: "blocked", count: b.blocked_count },
    { key: "failed", count: b.failed_count },
    { key: "recalled", count: b.recalled_count },
    { key: finished ? "canceled" : "queued", count: unsent },
  ];

  const startedMs = b.started_at ? new Date(b.started_at).getTime() : null;
  const speed = startedMs !== null && now > startedMs ? (processed * MS_PER_SECOND) / (now - startedMs) : 0;
  let pace: string | null = null;
  if (b.status === "SENDING" && speed > 0) {
    const seconds = (b.total_count - processed) / speed;
    const minutes = Math.ceil(seconds / SECONDS_PER_MINUTE);
    const speedText = new Intl.NumberFormat(i18n.language, { maximumFractionDigits: speed < 10 ? 1 : 0 }).format(speed);
    pace = `${t("broadcasts.details.speed", { speed: speedText })} · ${
      minutes <= 1 ? t("broadcasts.details.remainingSoon") : t("broadcasts.details.remaining", { count: minutes })
    }`;
  }

  return (
    <div className="glass-panel flex flex-col gap-2.5 rounded-3xl p-4">
      <div className="flex flex-wrap items-baseline gap-x-2.5 gap-y-1">
        <span className="text-[26px] font-bold tabular-nums tracking-tight text-foreground">
          {processed.toLocaleString(i18n.language)}{" "}
          <span className="text-[15px] font-medium text-muted-foreground">
            {t("broadcasts.details.of", { total: b.total_count.toLocaleString(i18n.language) })}
          </span>
        </span>
        {pace && <span className="text-[13px] text-muted-foreground">{pace}</span>}
        {startedMs !== null && (
          <span className="text-[12px] text-muted-foreground sm:ml-auto">
            {t("broadcasts.details.started", { date: formatDateTime(b.started_at!, i18n.language) })}
            {canRecall(b, now) && (
              <>
                {" · "}
                {t("broadcasts.details.recallUntil", {
                  date: formatDateTime(new Date(startedMs + RECALL_WINDOW_MS).toISOString(), i18n.language),
                })}
              </>
            )}
          </span>
        )}
      </div>
      <div className="flex h-2.5 overflow-hidden rounded-full glass-track">
        {segments
          .filter(({ key }) => key !== "queued")
          .map(({ key, count }) => (
            <span key={key} className={`${SEGMENT_CLASS[key]} transition-[width] duration-500`} style={{ width: share(count) }} />
          ))}
      </div>
      {/* every outcome with its count: the numbers the page has */}
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-[12px] text-foreground/80">
        {segments.map(({ key, count }) => (
          <span key={key} className="flex items-center gap-1.5">
            <span className={`size-2 rounded-full ${SEGMENT_CLASS[key]}`} />
            {t(`broadcasts.details.legend.${key}`)}
            <span className="font-semibold tabular-nums text-foreground">{count.toLocaleString(i18n.language)}</span>
          </span>
        ))}
      </div>
      {children && (
        // the line runs the panel's width; the rows' pills sit 6px in, their text on the status text's line
        <div className="-mx-4 mt-1.5 border-t border-white/[0.08] px-1.5 pt-2.5">{children}</div>
      )}
    </div>
  );
}
