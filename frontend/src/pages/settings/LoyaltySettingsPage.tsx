import { BadgePercent, Plus, Trash2 } from "lucide-react";
import { useState, type FormEvent, type KeyboardEvent, type PointerEvent } from "react";
import { useTranslation } from "react-i18next";

import { getLoyaltySettings, saveLoyaltySettings, type LoyaltySettings } from "@entities/loyalty/api";
import { usePermissions } from "@entities/user/use-current-user";
import { getErrorMessage } from "@shared/api/http";
import { currencySymbol } from "@shared/lib/format";
import { blockNonIntegerKeys } from "@shared/lib/number-input";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { Button } from "@shared/ui/Button";
import { Card } from "@shared/ui/Card";
import { CardHeader } from "@shared/ui/CardHeader";
import { ErrorState } from "@shared/ui/EmptyState";
import { FieldHint } from "@shared/ui/FieldHint";
import { IconButton } from "@shared/ui/IconButton";
import { Spinner } from "@shared/ui/Spinner";
import { Switch } from "@shared/ui/Switch";
import { SuffixInput } from "@shared/ui/TextInput";

const MAX_PERCENT = 100;
const MAX_TIERS = 20;
const SCALE_TICKS = [0, 25, 50, 75, 100];
const DEFAULT_TIERS = [
  { threshold: "1000", percent: "3" },
  { threshold: "5000", percent: "5" },
  { threshold: "15000", percent: "10" },
];

interface TierDraft {
  threshold: string;
  percent: string;
}

// mirrors the backend: positive thresholds, 1-100 percents, both strictly increasing
function invalidTiers(tiers: TierDraft[]): Set<number> {
  const invalid = new Set<number>();
  tiers.forEach((tier, index) => {
    const threshold = Number(tier.threshold);
    const percent = Number(tier.percent);
    const previous = tiers[index - 1];
    const isOwnInvalid =
      !(threshold > 0) || !Number.isInteger(percent) || percent < 1 || percent > MAX_PERCENT;
    const isOrderInvalid =
      previous !== undefined &&
      (threshold <= Number(previous.threshold) || percent <= Number(previous.percent));
    if (isOwnInvalid || isOrderInvalid) invalid.add(index);
  });
  return invalid;
}

export function LoyaltySettingsPage() {
  const { t } = useTranslation();
  const [isSaving, setIsSaving] = useState(false);
  const [enabled, setEnabled] = useState(false);
  const [windowText, setWindowText] = useState("");
  const [tiers, setTiers] = useState<TierDraft[]>([]);
  const [currency, setCurrency] = useState<string | null>(null);

  const permissions = usePermissions();
  const canManage = permissions.includes("LOYALTY_SETTINGS_MANAGE");
  const isLocked = !canManage || isSaving;
  const areSettingsLocked = isLocked || !enabled;

  const applySettings = (settings: LoyaltySettings) => {
    setEnabled(settings.enabled);
    setWindowText(settings.window_months === null ? "" : String(settings.window_months));
    setTiers(
      settings.tiers.length > 0
        ? settings.tiers.map((tier) => ({ threshold: tier.threshold, percent: String(tier.percent) }))
        : DEFAULT_TIERS,
    );
    setCurrency(settings.currency);
  };

  const [state] = useAsyncResource(getLoyaltySettings, { onSuccess: applySettings });

  const invalid = invalidTiers(tiers);
  // with no tiers the scale shows the defaults dimmed, as an example
  const chartTiers = tiers.length > 0 ? tiers : DEFAULT_TIERS;

  // a thumb stays between its neighbours: percents must strictly increase
  const setPercent = (index: number, percent: number) => {
    const low = (Number(tiers[index - 1]?.percent) || 0) + 1;
    const high = (Number(tiers[index + 1]?.percent) || MAX_PERCENT + 1) - 1;
    updateTier(index, { percent: String(Math.min(high, Math.max(low, Math.round(percent)))) });
  };

  const dragPercent = (index: number, event: PointerEvent<HTMLButtonElement>) => {
    const track = event.currentTarget.parentElement?.getBoundingClientRect();
    if (track) setPercent(index, ((event.clientX - track.left) / track.width) * MAX_PERCENT);
  };

  const stepPercent = (index: number, event: KeyboardEvent<HTMLButtonElement>) => {
    const delta = { ArrowRight: 1, ArrowUp: 1, ArrowLeft: -1, ArrowDown: -1 }[event.key];
    if (delta === undefined) return;
    event.preventDefault();
    setPercent(index, (Number(tiers[index]?.percent) || 0) + delta);
  };
  const isWindowInvalid = windowText !== "" && !(Number(windowText) >= 1);
  const hasInvalid = invalid.size > 0 || isWindowInvalid;
  const unit = currency ? currencySymbol(currency) : "";

  const updateTier = (index: number, patch: Partial<TierDraft>) =>
    setTiers((prev) => prev.map((tier, i) => (i === index ? { ...tier, ...patch } : tier)));

  const addTier = () =>
    setTiers((prev) => {
      const last = prev[prev.length - 1];
      if (!last) return DEFAULT_TIERS.slice(0, 1);
      return [
        ...prev,
        {
          threshold: String((Number(last.threshold) || 0) * 2),
          percent: String(Math.min(MAX_PERCENT, (Number(last.percent) || 0) + 2)),
        },
      ];
    });

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setIsSaving(true);
    try {
      applySettings(
        await saveLoyaltySettings({
          enabled,
          window_months: windowText === "" ? null : Number(windowText),
          tiers: tiers.map((tier) => ({ threshold: tier.threshold, percent: Number(tier.percent) })),
        }),
      );
      toast.success(t("loyalty.settings.saved"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("loyalty.settings.error")));
    } finally {
      setIsSaving(false);
    }
  };

  if (state.kind === "loading") return <Spinner size="page" />;
  if (state.kind === "error") return <ErrorState text={t("loyalty.settings.loadError")} size="page" />;

  return (
    <form onSubmit={(event) => void handleSubmit(event)}>
      <Card className="flex flex-col">
        <CardHeader
          icon={BadgePercent}
          title={t("loyalty.settings.title")}
          description={t("loyalty.settings.description")}
          aside={
            <>
              <span className="text-sm text-foreground/80">{t("loyalty.settings.enabledLabel")}</span>
              <FieldHint text={t("loyalty.settings.enabledHint")} />
              <Switch checked={enabled} onChange={setEnabled} disabled={isLocked} />
            </>
          }
        />

        <div className={`mt-4 flex flex-col gap-4 transition-opacity ${enabled ? "" : "opacity-45"}`}>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
            <label htmlFor="loyalty-window" className="flex items-center gap-1.5 text-sm text-foreground/80">
              {t("loyalty.settings.windowLabel")}
              <FieldHint text={t("loyalty.settings.windowHint")} />
            </label>
            <SuffixInput
              id="loyalty-window"
              type="number"
              min={1}
              step="1"
              onKeyDown={blockNonIntegerKeys}
              suffix={t("loyalty.settings.windowUnit", { count: Number(windowText) || 0 })}
              placeholder={t("loyalty.settings.windowAllTime")}
              value={windowText}
              disabled={areSettingsLocked}
              aria-invalid={isWindowInvalid}
              onChange={(event) => setWindowText(event.target.value)}
              className="w-44 shrink-0"
            />
          </div>

          <div className="flex flex-col gap-2">
            <span className="text-sm font-semibold text-foreground">{t("loyalty.settings.tiersTitle")}</span>
            <span className="text-[12px] text-muted-foreground">{t("loyalty.settings.tiersDescription")}</span>
            <div className="px-3 pb-6 pt-8">
              <div className="relative h-1.5 rounded-full bg-white/[0.07]">
                {SCALE_TICKS.map((tick) => (
                  <span
                    key={tick}
                    className="absolute top-4 -translate-x-1/2 text-[11.5px] text-muted-foreground"
                    style={{ left: `${tick}%` }}
                  >
                    {tick}%
                  </span>
                ))}
                {tiers.length === 0
                  ? chartTiers.map((tier, index) => (
                      <span
                        key={tier.threshold}
                        className="absolute top-1/2 flex size-6 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border-2 border-accent bg-canvas text-[11px] font-semibold opacity-30"
                        style={{ left: `${tier.percent}%` }}
                      >
                        {index + 1}
                      </span>
                    ))
                  : tiers.map((tier, index) => (
                      <button
                        key={index}
                        type="button"
                        disabled={areSettingsLocked}
                        onPointerDown={(event) => event.currentTarget.setPointerCapture(event.pointerId)}
                        onPointerMove={(event) => {
                          if (event.currentTarget.hasPointerCapture(event.pointerId)) dragPercent(index, event);
                        }}
                        onKeyDown={(event) => stepPercent(index, event)}
                        className={`absolute top-1/2 flex size-6 -translate-x-1/2 -translate-y-1/2 cursor-ew-resize touch-none items-center justify-center rounded-full border-2 bg-canvas text-[11px] font-semibold text-foreground outline-none focus-visible:z-10 focus-visible:ring-2 focus-visible:ring-accent/50 disabled:cursor-not-allowed ${
                          invalid.has(index) ? "border-error" : "border-accent"
                        }`}
                        style={{ left: `${Math.min(Number(tier.percent) || 0, MAX_PERCENT)}%` }}
                      >
                        {index + 1}
                      </button>
                    ))}
              </div>
            </div>

            {tiers.length === 0 && (
              <span className="text-[12px] text-muted-foreground opacity-60">{t("loyalty.settings.tiersEmpty")}</span>
            )}
            <div className="grid grid-cols-[repeat(auto-fill,minmax(10rem,1fr))] gap-2">
              {tiers.map((tier, index) => (
                <div key={index} className="flex flex-col gap-2 rounded-[14px] bg-white/[0.03] p-2.5">
                  <div className="flex items-center justify-between">
                    <span className="flex size-7 items-center justify-center rounded-full bg-white/[0.05] text-[12.5px] font-semibold text-foreground">
                      {index + 1}
                    </span>
                    <IconButton
                      size="8"
                      tone="danger"
                      disabled={areSettingsLocked}
                      onClick={() => setTiers((prev) => prev.filter((_, i) => i !== index))}
                    >
                      <Trash2 className="size-4" />
                    </IconButton>
                  </div>
                  <SuffixInput
                    type="number"
                    min={1}
                    max={MAX_PERCENT}
                    step="1"
                    onKeyDown={blockNonIntegerKeys}
                    suffix="%"
                    value={tier.percent}
                    disabled={areSettingsLocked}
                    aria-invalid={invalid.has(index)}
                    onChange={(event) => updateTier(index, { percent: event.target.value })}
                  />
                  <div className="flex items-center gap-2">
                    <span className="shrink-0 text-[13px] text-muted-foreground">{t("loyalty.settings.tierFrom")}</span>
                    <SuffixInput
                      type="number"
                      min={0}
                      step="0.01"
                      suffix={unit}
                      value={tier.threshold}
                      disabled={areSettingsLocked}
                      aria-invalid={invalid.has(index)}
                      onChange={(event) => updateTier(index, { threshold: event.target.value })}
                      className="min-w-0 flex-1"
                    />
                  </div>
                </div>
              ))}
              {canManage && tiers.length < MAX_TIERS && (
                <button
                  type="button"
                  onClick={addTier}
                  disabled={areSettingsLocked}
                  className="flex min-h-36 items-center justify-center gap-1.5 rounded-[14px] border border-dashed border-white/[0.12] text-[13px] font-semibold text-muted-foreground transition-colors hover:bg-white/[0.03] hover:text-foreground disabled:cursor-not-allowed disabled:opacity-60"
                >
                  <Plus className="size-4" />
                  {t("loyalty.settings.addTier")}
                </button>
              )}
            </div>
          </div>
        </div>

        {canManage && (
          <div className="-mx-4 mt-4 flex justify-end border-t border-white/[0.07] px-4 pt-4">
            <Button variant="accent" type="submit" disabled={isSaving || hasInvalid}>
              {isSaving ? t("common.saving") : t("common.save")}
            </Button>
          </div>
        )}
      </Card>
    </form>
  );
}
