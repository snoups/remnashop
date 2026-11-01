import { BadgePercent, Plus, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import {
  getLoyaltySettings,
  resetLoyaltySettings,
  saveLoyaltySettings,
  type LoyaltySettings,
} from "@entities/loyalty/api";
import { usePermissions } from "@entities/user/use-current-user";
import { getErrorMessage } from "@shared/api/http";
import { currencySymbol } from "@shared/lib/format";
import { blockNonIntegerKeys } from "@shared/lib/number-input";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { Button } from "@shared/ui/Button";
import { Card } from "@shared/ui/Card";
import { CardHeader } from "@shared/ui/CardHeader";
import { EYEBROW_CLASS, LIST_BODY_CLASS, LIST_ROW_CLASS } from "@shared/ui/classes";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { ErrorState } from "@shared/ui/EmptyState";
import { FieldHint } from "@shared/ui/FieldHint";
import { IconButton } from "@shared/ui/IconButton";
import { Slider } from "@shared/ui/Slider";
import { Spinner } from "@shared/ui/Spinner";
import { Switch } from "@shared/ui/Switch";
import { SegmentedPills } from "@shared/ui/SegmentedPills";
import { SuffixInput } from "@shared/ui/TextInput";
import { ListRow } from "@shared/ui/ListRow";

const MAX_PERCENT = 100;
const MAX_TIERS = 20;
// 0 stands for all time (window_months: null)
const WINDOW_MONTHS = [0, 1, 3, 6, 12];
const SCALE_TICKS = [0, 25, 50, 75, 100];
const TIER_ROW_CLASS = "grid grid-cols-[1.75rem_minmax(8rem,12rem)_minmax(0,1fr)_6rem_2rem] items-center gap-3";
const DEFAULT_TIERS = [
  { threshold: "10", percent: "3" },
  { threshold: "30", percent: "5" },
  { threshold: "50", percent: "7" },
  { threshold: "100", percent: "10" },
  { threshold: "200", percent: "12" },
  { threshold: "500", percent: "15" },
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
  const [isResetting, setIsResetting] = useState(false);
  const [isResetConfirmOpen, setIsResetConfirmOpen] = useState(false);
  const [enabled, setEnabled] = useState(false);
  const [windowMonths, setWindowMonths] = useState(0);
  const [tiers, setTiers] = useState<TierDraft[]>([]);
  const [currency, setCurrency] = useState<string | null>(null);

  const permissions = usePermissions();
  const canManage = permissions.includes("LOYALTY_SETTINGS_MANAGE");
  const canReset = permissions.includes("LOYALTY_SETTINGS_RESET");
  const isLocked = !canManage || isSaving;
  const areSettingsLocked = isLocked || !enabled;

  const applySettings = (settings: LoyaltySettings) => {
    setEnabled(settings.enabled);
    setWindowMonths(settings.window_months ?? 0);
    setTiers(
      settings.tiers.length > 0
        ? settings.tiers.map((tier) => ({ threshold: tier.threshold, percent: String(tier.percent) }))
        : DEFAULT_TIERS,
    );
    setCurrency(settings.currency);
  };

  const [state] = useAsyncResource(getLoyaltySettings, { onSuccess: applySettings });

  const invalid = invalidTiers(tiers);
  const hasInvalid = invalid.size > 0;
  // a stored window outside the presets stays selectable
  const windowOptions = [...new Set([...WINDOW_MONTHS, windowMonths])]
    .sort((a, b) => a - b)
    .map((months) => ({
      value: months,
      label:
        months === 0
          ? t("loyalty.settings.windowAllTime")
          : `${months} ${t("loyalty.settings.windowUnit", { count: months })}`,
    }));
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

  // a slider stays between its neighbours: percents must strictly increase
  const slidePercent = (index: number, percent: number) => {
    const low = (Number(tiers[index - 1]?.percent) || 0) + 1;
    const high = (Number(tiers[index + 1]?.percent) || MAX_PERCENT + 1) - 1;
    updateTier(index, { percent: String(Math.min(high, Math.max(low, percent))) });
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setIsSaving(true);
    try {
      applySettings(
        await saveLoyaltySettings({
          enabled,
          window_months: windowMonths === 0 ? null : windowMonths,
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

  const handleReset = async () => {
    setIsResetConfirmOpen(false);
    setIsResetting(true);
    try {
      applySettings(await resetLoyaltySettings());
      toast.success(t("loyalty.settings.resetSuccess"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("loyalty.settings.resetError")));
    } finally {
      setIsResetting(false);
    }
  };

  if (state.kind === "loading") return <Spinner size="page" />;
  if (state.kind === "error") {
    return (
      <Card>
        <CardHeader icon={BadgePercent} title={t("loyalty.settings.title")} description={t("loyalty.settings.description")} />
        <ErrorState text={t("common.loadError")} />
      </Card>
    );
  }

  return (
    <form onSubmit={(event) => void handleSubmit(event)}>
      <Card className="flex flex-col">
        <CardHeader
          icon={BadgePercent}
          title={t("loyalty.settings.title")}
          description={t("loyalty.settings.description")}
          aside={
            <>
              <FieldHint text={t("loyalty.settings.enabledHint")} side="bottom" align="end" />
              <Switch checked={enabled} onChange={setEnabled} disabled={isLocked} />
            </>
          }
        />

        <div className={`mt-4 flex flex-col gap-4 transition-opacity ${enabled ? "" : "opacity-45"}`}>
          <div className="flex flex-wrap items-center justify-end gap-x-4 gap-y-2">
            <span className="mr-auto text-sm text-foreground/80">{t("loyalty.settings.windowLabel")}</span>
            <SegmentedPills
              value={windowMonths}
              onChange={setWindowMonths}
              disabled={areSettingsLocked}
              options={windowOptions}
            />
          </div>

          <div className="flex flex-col gap-2">
            <div className="overflow-x-auto">
              <div className="min-w-[40rem]">
                <div className={`${TIER_ROW_CLASS} border-b border-border px-3 pb-2.5`}>
                  <span />
                  <span className={EYEBROW_CLASS}>{t("loyalty.settings.thresholdColumn")}</span>
                  <span className={`flex justify-between ${EYEBROW_CLASS}`}>
                    {SCALE_TICKS.map((tick) => (
                      <span key={tick}>{tick}%</span>
                    ))}
                  </span>
                  <span className={EYEBROW_CLASS}>{t("loyalty.settings.percentColumn")}</span>
                  <span />
                </div>
                <div className={LIST_BODY_CLASS}>
                  {(tiers.length > 0 ? tiers : DEFAULT_TIERS).map((tier, index) => {
                    const isExample = tiers.length === 0;
                    const isDisabled = areSettingsLocked || isExample;
                    return (
                      <div
                        key={index}
                        className={`${TIER_ROW_CLASS} ${LIST_ROW_CLASS} ${isExample ? "opacity-30" : ""} ${isDisabled ? "" : "hover:bg-white/[0.04]"}`}
                      >
                        <span className="flex size-7 items-center justify-center rounded-full bg-white/[0.05] text-[12.5px] font-semibold text-foreground">
                          {index + 1}
                        </span>
                        <SuffixInput
                          type="number"
                          min={0}
                          step="0.01"
                          suffix={unit}
                          value={tier.threshold}
                          disabled={isDisabled}
                          aria-invalid={invalid.has(index)}
                          onChange={(event) => updateTier(index, { threshold: event.target.value })}
                        />
                        <Slider
                          max={MAX_PERCENT}
                          value={Number(tier.percent) || 0}
                          disabled={isDisabled}
                          onChange={(percent) => slidePercent(index, percent)}
                          className="w-full"
                        />
                        <SuffixInput
                          type="number"
                          min={1}
                          max={MAX_PERCENT}
                          step="1"
                          onKeyDown={blockNonIntegerKeys}
                          suffix="%"
                          value={tier.percent}
                          disabled={isDisabled}
                          aria-invalid={invalid.has(index)}
                          onChange={(event) => updateTier(index, { percent: event.target.value })}
                        />
                        {isExample ? (
                          <span />
                        ) : (
                          <IconButton
                            size="8"
                            tone="danger"
                            disabled={areSettingsLocked}
                            onClick={() => setTiers((prev) => prev.filter((_, i) => i !== index))}
                          >
                            <Trash2 className="size-4" />
                          </IconButton>
                        )}
                      </div>
                    );
                  })}
                  {canManage && tiers.length < MAX_TIERS && (
                    <ListRow
                      type="button"
                      onClick={addTier}
                      disabled={areSettingsLocked}
                      className={`${TIER_ROW_CLASS} text-[13px] font-medium text-muted-foreground hover:text-foreground disabled:cursor-not-allowed disabled:hover:bg-transparent disabled:hover:text-muted-foreground`}
                    >
                      <span className="flex size-7 items-center justify-center rounded-full border border-dashed border-white/[0.18]">
                        <Plus className="size-3.5" />
                      </span>
                      <span className="col-span-4">{t("loyalty.settings.addTier")}</span>
                    </ListRow>
                  )}
                </div>
              </div>
            </div>
            {tiers.length === 0 && (
              <span className="text-[12px] text-muted-foreground">{t("loyalty.settings.tiersEmpty")}</span>
            )}
          </div>
        </div>

        {(canManage || canReset) && (
          <div className="mt-4 flex flex-wrap items-center gap-2">
            {canManage && (
              <Button variant="accent" type="submit" disabled={isSaving || hasInvalid}>
                {isSaving ? t("common.saving") : t("common.save")}
              </Button>
            )}
            {canReset && (
              <Button variant="outline" type="button" onClick={() => setIsResetConfirmOpen(true)} disabled={isResetting}>
                {t("common.reset")}
              </Button>
            )}
          </div>
        )}
      </Card>

      {isResetConfirmOpen && (
        <ConfirmDialog
          title={t("loyalty.settings.resetConfirmTitle")}
          message={t("loyalty.settings.resetConfirmText")}
          confirmLabel={t("common.reset")}
          cancelLabel={t("common.cancel")}
          danger
          onConfirm={() => void handleReset()}
          onCancel={() => setIsResetConfirmOpen(false)}
        />
      )}
    </form>
  );
}
