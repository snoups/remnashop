import { useTranslation } from "react-i18next";

import type { AudiencePreview, BroadcastCategory, BroadcastChannel } from "@entities/broadcasts/api";
import type { AsyncState } from "@shared/lib/use-async-resource";
import { Card } from "@shared/ui/Card";
import { EYEBROW_CLASS } from "@shared/ui/classes";
import { Spinner } from "@shared/ui/Spinner";

const CHANNELS: BroadcastChannel[] = ["TELEGRAM", "EMAIL"];

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
    <Card className="flex flex-col gap-2.5">
      <span className={EYEBROW_CLASS}>{t("broadcasts.editor.recipients.title")}</span>
      {state.kind === "loading" && <Spinner />}
      {state.kind === "error" && (
        <span className="text-[12.5px] text-error">{t("broadcasts.editor.recipients.error")}</span>
      )}
      {state.kind === "ready" && (
        <>
          <span className="text-[30px] font-bold tabular-nums text-foreground">{format(total)}</span>
          {channelCounts.length > 0 && (
            <span className="text-[12.5px] text-foreground/80">
              {channelCounts
                .map(([channel, n]) => `${t(`broadcasts.channel.${channel}`)}: ${format(n)}`)
                .join(" · ")}
            </span>
          )}
          {rows.map((row) => (
            <div key={row.key} className="flex flex-col gap-1">
              <div className="flex justify-between text-[12.5px]">
                <span className="text-foreground/80">{row.label}</span>
                <span className="tabular-nums text-foreground">{format(row.count)}</span>
              </div>
              <span className="h-[5px] overflow-hidden rounded-full bg-white/[0.07]">
                <span
                  className={`block h-full rounded-full ${row.other ? "bg-muted-foreground" : "bg-primary"}`}
                  style={{ width: `${total > 0 ? (row.count / total) * 100 : 0}%` }}
                />
              </span>
            </div>
          ))}
        </>
      )}
      <span className="text-[12px] leading-normal text-muted-foreground">
        {t(category === "MARKETING" ? "broadcasts.editor.recipients.excludedMarketing" : "broadcasts.editor.recipients.excluded")}
      </span>
    </Card>
  );
}
