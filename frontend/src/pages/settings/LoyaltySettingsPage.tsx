import { BadgePercent, Plus, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
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
const FIRST_TIER = { threshold: "1000", percent: "3" };

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
  // the badge shows what's stored, not the unsaved toggle
  const [savedEnabled, setSavedEnabled] = useState(false);
  const [windowText, setWindowText] = useState("");
  const [tiers, setTiers] = useState<TierDraft[]>([]);
  const [currency, setCurrency] = useState<string | null>(null);

  const permissions = usePermissions();
  const canManage = permissions.includes("LOYALTY_SETTINGS_MANAGE");
  const isLocked = !canManage || isSaving;
  const areSettingsLocked = isLocked || !enabled;

  const applySettings = (settings: LoyaltySettings) => {
    setEnabled(settings.enabled);
    setSavedEnabled(settings.enabled);
    setWindowText(settings.window_months === null ? "" : String(settings.window_months));
    setTiers(settings.tiers.map((tier) => ({ threshold: tier.threshold, percent: String(tier.percent) })));
    setCurrency(settings.currency);
  };

  const [state] = useAsyncResource(getLoyaltySettings, { onSuccess: applySettings });

  const invalid = invalidTiers(tiers);
  const isWindowInvalid = windowText !== "" && !(Number(windowText) >= 1);
  const hasInvalid = invalid.size > 0 || isWindowInvalid;
  const unit = currency ? currencySymbol(currency) : "";

  const updateTier = (index: number, patch: Partial<TierDraft>) =>
    setTiers((prev) => prev.map((tier, i) => (i === index ? { ...tier, ...patch } : tier)));

  const addTier = () =>
    setTiers((prev) => {
      const last = prev[prev.length - 1];
      if (!last) return [FIRST_TIER];
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
    <form onSubmit={(event) => void handleSubmit(event)} className="max-w-2xl">
      <Card className="flex flex-col">
        <CardHeader
          icon={BadgePercent}
          title={t("loyalty.settings.title")}
          description={t("loyalty.settings.description")}
          aside={
            <span
              className={`flex h-9 shrink-0 items-center rounded-full px-4 text-[13px] font-semibold ${
                savedEnabled ? "bg-success/10 text-success" : "bg-white/[0.05] text-muted-foreground"
              }`}
            >
              {savedEnabled ? t("loyalty.settings.status.enabled") : t("loyalty.settings.status.disabled")}
            </span>
          }
        />

        <div className="mt-4 flex items-center justify-between gap-3 py-1">
          <span className="flex items-center gap-1.5 text-sm text-foreground/80">
            {t("loyalty.settings.enabledLabel")}
            <FieldHint text={t("loyalty.settings.enabledHint")} />
          </span>
          <Switch checked={enabled} onChange={setEnabled} disabled={isLocked} />
        </div>

        <div className={`mt-3.5 flex flex-col gap-4 transition-opacity ${enabled ? "" : "opacity-45"}`}>
          <div className="flex items-center justify-between gap-3">
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
            {tiers.map((tier, index) => (
              <div key={index} className="flex items-center gap-2 rounded-[14px] bg-white/[0.03] px-3 py-2">
                <span className="w-8 shrink-0 text-[13px] text-muted-foreground">{t("loyalty.settings.tierFrom")}</span>
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
                  className="w-28 shrink-0"
                />
                <IconButton
                  size="8"
                  tone="danger"
                  disabled={areSettingsLocked}
                  onClick={() => setTiers((prev) => prev.filter((_, i) => i !== index))}
                >
                  <Trash2 className="size-4" />
                </IconButton>
              </div>
            ))}
            <Button
              variant="outline"
              className="w-fit"
              type="button"
              onClick={addTier}
              disabled={areSettingsLocked || tiers.length >= MAX_TIERS}
            >
              <Plus className="size-4" />
              {t("loyalty.settings.addTier")}
            </Button>
          </div>
        </div>

        {canManage && (
          <Button variant="accent" className="mt-4 w-fit" type="submit" disabled={isSaving || hasInvalid}>
            {isSaving ? t("common.saving") : t("common.save")}
          </Button>
        )}
      </Card>
    </form>
  );
}
