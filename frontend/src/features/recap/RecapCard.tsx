import { useMemo } from "react";
import type { Ref } from "react";
import { useTranslation } from "react-i18next";

import { BrandMark } from "@entities/appearance/BrandMark";
import {
  useBrandName,
  useEffectiveAccentColor,
  useEffectiveShaderEnabled,
  useEffectiveShaderPalette,
} from "@entities/appearance/use-appearance";
import type { Recap } from "@entities/overview/api";
import { DEFAULT_ACCENT_COLOR, DEFAULT_SHADER_PALETTE_HEX, hexToHueDegrees } from "@shared/lib/color";
import { formatMoney } from "@shared/lib/format";
import { parseIsoDate } from "@shared/lib/iso-date";
import { renderShaderGradientImage } from "@shared/lib/shader-gradient";
import { EYEBROW_CLASS } from "@shared/ui/classes";

export type RecapBlock = "totals" | "month" | "infra";
export type RecapField = "revenueTotal" | "monthRevenue" | "customers" | "payers";

const MASK = "🙈";

// the card is drawn over the dashboard's own shader, as a still frame: a PNG snapshot can't see the
// live canvas behind the page. The panel's glass goes over it, as on every page
const CARD_CLASS =
  "relative isolate flex w-[400px] flex-col gap-5 overflow-hidden rounded-3xl border border-white/[0.1] bg-surface bg-cover bg-center p-6 shadow-[inset_0_1px_0_rgb(255_255_255/0.12)]";
// the shader frame's size: a soft gradient, upscaled for the 2x PNG without losing anything
const SHADER_WIDTH = 400;
const SHADER_HEIGHT = 720;
// the shader turned off in appearance settings: accent glows instead
const GLOW_STYLE = {
  background:
    "radial-gradient(60% 50% at 15% 0%, color-mix(in srgb, var(--color-primary) 28%, transparent), transparent 70%), radial-gradient(50% 40% at 100% 100%, color-mix(in srgb, var(--color-primary) 16%, transparent), transparent 70%)",
};
const LINE_CLASS = "h-px bg-gradient-to-r from-transparent via-primary/30 to-transparent";

// the same palette and accent hue as the live background
function useShaderFrame(): string | null {
  const enabled = useEffectiveShaderEnabled();
  const accent = useEffectiveAccentColor();
  const palette = useEffectiveShaderPalette() ?? DEFAULT_SHADER_PALETTE_HEX;
  const paletteKey = palette.join(",");
  return useMemo(() => {
    if (!enabled) return null;
    const hueDegrees = accent ? hexToHueDegrees(accent) - hexToHueDegrees(DEFAULT_ACCENT_COLOR) : 0;
    return renderShaderGradientImage({
      width: SHADER_WIDTH,
      height: SHADER_HEIGHT,
      palette: paletteKey.split(","),
      hueRadians: (hueDegrees * Math.PI) / 180,
    });
  }, [enabled, accent, paletteKey]);
}

function Stat({ value, label, accent = false }: { value: string; label: string; accent?: boolean }) {
  return (
    <div className="flex min-w-0 flex-col gap-1">
      <span className={`truncate text-[20px] font-bold tabular-nums tracking-tight ${accent ? "text-primary" : "text-foreground"}`}>
        {value}
      </span>
      {/* two lines held for every label, so the values of a row stay level */}
      <span className={`line-clamp-2 min-h-[2lh] whitespace-pre-line ${EYEBROW_CLASS}`}>{label}</span>
    </div>
  );
}

/** The shop's recap as a shareable card: all-time revenue as the hero, then the chosen blocks. */
export function RecapCard({
  recap,
  version,
  blocks,
  hidden,
  note,
  ref,
}: {
  recap: Recap;
  version: string | null;
  blocks: RecapBlock[];
  hidden: RecapField[];
  note: string;
  ref?: Ref<HTMLDivElement>;
}) {
  const { t, i18n } = useTranslation();
  const language = i18n.language;
  const brandName = useBrandName();
  const compact = new Intl.NumberFormat(language, { notation: "compact", maximumFractionDigits: 1 });
  const mask = (field: RecapField, text: string) => (hidden.includes(field) ? MASK : text);
  const money = (field: RecapField, value: string) => mask(field, formatMoney(value, recap.report_currency, language));
  const count = (value: number) => compact.format(value);
  const month = new Intl.DateTimeFormat(language, { month: "long", year: "numeric" }).format(new Date());
  const sinceDate = parseIsoDate(recap.since);
  const since = sinceDate
    ? new Intl.DateTimeFormat(language, { day: "numeric", month: "long", year: "numeric" }).format(sinceDate)
    : recap.since;
  const showInfra = blocks.includes("infra") && recap.nodes !== null && recap.countries !== null;
  const shader = useShaderFrame();

  return (
    <div ref={ref} className={CARD_CLASS} style={shader ? { backgroundImage: `url(${shader})` } : undefined}>
      <div className={`pointer-events-none absolute inset-0 -z-10 ${shader ? "glass-panel" : ""}`} style={shader ? undefined : GLOW_STYLE} />
      <div className="flex items-center gap-2">
        <BrandMark className="size-6 text-primary" />
        <span className="text-[15px] font-semibold tracking-tight text-foreground">{brandName}</span>
      </div>
      <div className="flex flex-col items-center gap-1.5 py-2 text-center">
        <span className="text-[44px] font-bold leading-none tabular-nums tracking-tight text-primary">
          {money("revenueTotal", recap.revenue_total)}
        </span>
        <span className={EYEBROW_CLASS}>{t("recap.revenueTotal")}</span>
      </div>
      {blocks.includes("totals") && (
        <>
          <div className={LINE_CLASS} />
          <div className="grid grid-cols-3 gap-3">
            <Stat value={mask("customers", count(recap.customers))} label={t("recap.customers")} />
            <Stat value={mask("payers", count(recap.payers))} label={t("recap.payers")} />
            <Stat value={count(recap.active_subscriptions)} label={t("recap.activeSubscriptions")} />
          </div>
        </>
      )}
      {blocks.includes("month") && (
        <>
          <div className={LINE_CLASS} />
          <div className="flex flex-col gap-3">
            <span className="text-[13px] font-semibold capitalize text-foreground">{month}</span>
            <div className="grid grid-cols-3 gap-3">
              <Stat value={money("monthRevenue", recap.month_revenue)} label={t("recap.monthRevenue")} accent />
              <Stat value={count(recap.new_customers)} label={t("recap.newCustomers")} />
              <Stat value={count(recap.new_payers)} label={t("recap.newPayers")} />
            </div>
          </div>
        </>
      )}
      {showInfra && (
        <>
          <div className={LINE_CLASS} />
          <div className="flex flex-col gap-3">
            <span className="text-[13px] font-semibold text-foreground">{t("recap.blocks.infra")}</span>
            <div className="grid grid-cols-3 gap-3">
              <Stat value={count(recap.nodes ?? 0)} label={t("recap.nodes")} />
              <Stat value={count(recap.countries ?? 0)} label={t("recap.countries")} />
              <Stat value={count(recap.transactions)} label={t("recap.transactions")} />
            </div>
          </div>
        </>
      )}
      <div className={LINE_CLASS} />
      <div className="flex flex-col gap-2">
        {note && <p className="text-center text-[13px] font-medium text-primary">{note}</p>}
        <div className="flex items-center justify-between gap-3 text-[12px]">
          <span className="font-medium text-primary">{t("recap.since", { date: since })}</span>
          {version && (
            <span className="rounded-full bg-primary/10 px-2 py-0.5 font-mono text-[11px] text-primary/80">v{version}</span>
          )}
        </div>
      </div>
    </div>
  );
}
