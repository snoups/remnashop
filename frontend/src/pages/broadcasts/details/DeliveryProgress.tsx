import { useTranslation } from "react-i18next";

import { RECALL_WINDOW_MS } from "@entities/broadcasts/api";
import type { Broadcast } from "@entities/broadcasts/api";
import { canRecall, processedCount } from "@entities/broadcasts/display";
import { formatDateTime } from "@shared/lib/relative-time";
import { Card } from "@shared/ui/Card";

const MS_PER_SECOND = 1000;
const SECONDS_PER_MINUTE = 60;

interface DeliveryProgressProps {
  broadcast: Broadcast;
  now: number;
}

const LEGEND = [
  { key: "delivered", dot: "bg-success" },
  { key: "blocked", dot: "bg-warning" },
  { key: "failed", dot: "bg-error" },
  { key: "queued", dot: "bg-white/20" },
] as const;

export function DeliveryProgress({ broadcast: b, now }: DeliveryProgressProps) {
  const { t, i18n } = useTranslation();
  const processed = processedCount(b);
  const share = (n: number) => (b.total_count > 0 ? `${(n / b.total_count) * 100}%` : "0%");

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
    <Card className="flex flex-col gap-2.5">
      <div className="flex flex-wrap items-baseline gap-x-2.5 gap-y-1">
        <span className="text-[26px] font-bold tabular-nums text-foreground">
          {processed.toLocaleString(i18n.language)}{" "}
          <span className="text-[15px] font-medium text-muted-foreground">
            {t("broadcasts.details.of", { total: b.total_count.toLocaleString(i18n.language) })}
          </span>
        </span>
        {pace && <span className="text-[13px] text-muted-foreground">{pace}</span>}
        {startedMs !== null && (
          <span className="text-[12.5px] text-muted-foreground sm:ml-auto">
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
      <div className="flex h-2.5 overflow-hidden rounded-full bg-white/[0.07]">
        <span className="bg-success transition-[width] duration-500" style={{ width: share(b.sent_count) }} />
        <span className="bg-warning transition-[width] duration-500" style={{ width: share(b.blocked_count) }} />
        <span className="bg-error transition-[width] duration-500" style={{ width: share(b.failed_count) }} />
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-[12.5px] text-foreground/80">
        {LEGEND.map(({ key, dot }) => (
          <span key={key} className="flex items-center gap-1.5">
            <span className={`size-2 rounded-full ${dot}`} />
            {t(`broadcasts.details.legend.${key}`)}
          </span>
        ))}
      </div>
    </Card>
  );
}
