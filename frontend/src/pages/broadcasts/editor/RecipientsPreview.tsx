import { Languages, Mail, Send, Users } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { AudiencePreview, BroadcastCategory, BroadcastChannel } from "@entities/broadcasts/api";
import type { AsyncState } from "@shared/lib/use-async-resource";
import { KPI_VALUE_CLASS } from "@shared/ui/classes";
import { IconCircle } from "@shared/ui/glass/IconCircle";
import { Section } from "@shared/ui/glass/Section";
import { Spinner } from "@shared/ui/Spinner";

const CHANNELS: BroadcastChannel[] = ["TELEGRAM", "EMAIL"];
const CHANNEL_ICON: Record<BroadcastChannel, LucideIcon> = { TELEGRAM: Send, EMAIL: Mail };

interface RecipientsPreviewProps {
  state: AsyncState<AudiencePreview>;
  category: BroadcastCategory;
  defaultLocale: string;
  /** locales with their own text; the rest get the default one */
  contentLocales: string[];
}

export function RecipientsPreview({ state, category, defaultLocale, contentLocales }: RecipientsPreviewProps) {
  const { t, i18n } = useTranslation();
  const format = (n: number) => n.toLocaleString(i18n.language);

  let rows: { key: string; label: string; count: number; other: boolean }[] = [];
  if (state.kind === "ready") {
    const counts = state.data.by_locale;
    rows = contentLocales.map((locale) => ({
      key: locale,
      label: locale.toUpperCase(),
      count: counts[locale] ?? 0,
      other: false,
    }));
    const others = Object.entries(counts)
      .filter(([locale]) => !contentLocales.includes(locale))
      .reduce((sum, [, n]) => sum + n, 0);
    if (others > 0) {
      rows.push({
        key: "other",
        label: t("broadcasts.editor.recipients.others", { locale: defaultLocale.toUpperCase() }),
        count: others,
        other: true,
      });
    }
  }
  const channelCounts =
    state.kind === "ready"
      ? CHANNELS.map((channel) => [channel, state.data.by_channel[channel] ?? 0] as const).filter(([, n]) => n > 0)
      : [];
  const total = state.kind === "ready" ? state.data.total : 0;

  return (
    <Section
      icon={Users}
      title={t("broadcasts.editor.recipients.title")}
      description={t(category === "MARKETING" ? "broadcasts.editor.recipients.excludedMarketing" : "broadcasts.editor.recipients.excluded")}
    >
      <div className="mt-4 flex flex-col gap-3 px-3.5 pb-2">
      {state.kind === "loading" && <Spinner />}
      {state.kind === "error" && (
        <span className="text-[12px] text-error">{t("broadcasts.editor.recipients.error")}</span>
      )}
      {state.kind === "ready" && (
        <>
          <div className="flex items-baseline gap-2">
            <span className={`${KPI_VALUE_CLASS} text-foreground`}>{format(total)}</span>
            <span className="text-[13px] text-muted-foreground">{t("broadcasts.editor.recipients.title").toLowerCase()}</span>
          </div>
          {/* a share bar each, of the total: one customer can be counted on both channels */}
          {channelCounts.length > 0 && (
            <div className="flex flex-col gap-3">
              {channelCounts.map(([channel, n]) => (
                <ShareLine
                  key={channel}
                  icon={CHANNEL_ICON[channel]}
                  label={t(`broadcasts.channel.${channel}`)}
                  value={format(n)}
                  share={total > 0 ? n / total : 0}
                />
              ))}
            </div>
          )}
          {channelCounts.length > 0 && rows.length > 0 && <div className="h-px bg-white/[0.08]" />}
          {rows.length > 0 && (
            <div className="flex flex-col gap-3">
              {rows.map((row) => (
                <ShareLine
                  key={row.key}
                  icon={Languages}
                  label={row.label}
                  value={format(row.count)}
                  share={total > 0 ? row.count / total : 0}
                  muted={row.other}
                />
              ))}
            </div>
          )}
        </>
      )}
      </div>
    </Section>
  );
}

/** A channel or language: icon, name, count, and its share of the total as a bar. */
function ShareLine({
  icon: Icon,
  label,
  value,
  share,
  muted = false,
}: {
  icon: LucideIcon;
  label: string;
  value: string;
  share: number;
  /** the "others get the default" line */
  muted?: boolean;
}) {
  return (
    <div className="flex items-center gap-3">
      <IconCircle icon={Icon} />
      <div className="flex min-w-0 flex-1 flex-col gap-1.5">
        <div className="flex items-center justify-between gap-3 text-[13px]">
          <span className={`truncate ${muted ? "text-muted-foreground" : "text-foreground"}`}>{label}</span>
          <span className="shrink-0 font-semibold tabular-nums text-foreground">{value}</span>
        </div>
        <span className="h-1 overflow-hidden rounded-full glass-track">
          <span
            className={`block h-full rounded-full ${muted ? "bg-muted-foreground" : "bg-primary"}`}
            style={{ width: `${share * 100}%` }}
          />
        </span>
      </div>
    </div>
  );
}
