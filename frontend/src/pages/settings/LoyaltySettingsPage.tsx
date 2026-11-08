import { BadgePercent, CalendarDays, Plus, Power, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import {
  getLoyaltySettings,
  resetLoyaltySettings,
  saveLoyaltySettings,
  type LoyaltySettings,
} from "@entities/loyalty/api";
import { usePermissions } from "@entities/user/use-current-user";
import { LoyaltyGuideDialog } from "@pages/settings/LoyaltyGuideDialog";
import { getErrorMessage } from "@shared/api/http";
import { currencySymbol } from "@shared/lib/format";
import { blockNonIntegerKeys } from "@shared/lib/number-input";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { Button } from "@shared/ui/Button";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { EYEBROW_CLASS } from "@shared/ui/classes";
import { ErrorState } from "@shared/ui/glass/EmptyState";
import { IconCircle } from "@shared/ui/glass/IconCircle";
import { Input } from "@shared/ui/glass/Input";
import { Row } from "@shared/ui/glass/Row";
import { Section, SectionRows } from "@shared/ui/glass/Section";
import { StatusPill } from "@shared/ui/glass/StatusPill";
import { Switch } from "@shared/ui/glass/Switch";
import { IconButton } from "@shared/ui/IconButton";
import { PillTabs } from "@shared/ui/PillTabs";
import { SaveFooter } from "@shared/ui/SaveFooter";
import { Slider } from "@shared/ui/Slider";
import { Spinner } from "@shared/ui/Spinner";

const MAX_PERCENT = 100;
const MAX_TIERS = 20;
// Numeric(10, 2) on the backend
const THRESHOLD_FORMAT = /^\d{1,8}(\.\d{1,2})?$/;
// 0 stands for all time (window_months: null)
const WINDOW_MONTHS = [0, 1, 3, 6, 12];
const SCALE_TICKS = [0, 25, 50, 75, 100];
const TIER_ROW_CLASS = "grid grid-cols-[2rem_minmax(8rem,12rem)_minmax(0,1fr)_6rem_2rem] items-center gap-3";
// the first level added by hand to an emptied list
const FIRST_TIER = { threshold: "10", percent: "3" };

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
      !THRESHOLD_FORMAT.test(tier.threshold) || !(threshold > 0) || !Number.isInteger(percent) || percent < 1 || percent > MAX_PERCENT;
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
  const [saved, setSaved] = useState<LoyaltySettings | null>(null);
  // shown once a save was tried, gone as soon as a level is added or the program switched off
  const [showTiersError, setShowTiersError] = useState(false);

  const permissions = usePermissions();
  const canManage = permissions.includes("LOYALTY_SETTINGS_MANAGE");
  const canReset = permissions.includes("LOYALTY_SETTINGS_RESET");
  const isLocked = !canManage || isSaving;
  const areSettingsLocked = isLocked || !enabled;

  const applySettings = (settings: LoyaltySettings) => {
    setSaved(settings);
    setEnabled(settings.enabled);
    setWindowMonths(settings.window_months ?? 0);
    setTiers(settings.tiers.map((tier) => ({ threshold: tier.threshold, percent: String(tier.percent) })));
    setCurrency(settings.currency);
  };

  const [state] = useAsyncResource(getLoyaltySettings, { onSuccess: applySettings });

  const invalid = invalidTiers(tiers);
  const hasInvalid = invalid.size > 0;
  const needsTier = enabled && tiers.length === 0;
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
  const dirty =
    saved !== null &&
    (enabled !== saved.enabled ||
      windowMonths !== (saved.window_months ?? 0) ||
      tiers.length !== saved.tiers.length ||
      tiers.some(
        (tier, index) =>
          tier.threshold !== saved.tiers[index]?.threshold || tier.percent !== String(saved.tiers[index]?.percent),
      ));

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

  // a slider stays between its neighbours: percents must strictly increase
  const slidePercent = (index: number, percent: number) => {
    const low = (Number(tiers[index - 1]?.percent) || 0) + 1;
    const high = (Number(tiers[index + 1]?.percent) || MAX_PERCENT + 1) - 1;
    updateTier(index, { percent: String(Math.min(high, Math.max(low, percent))) });
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (needsTier) {
      setShowTiersError(true);
      return;
    }
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
      <Section icon={BadgePercent} title={t("loyalty.settings.title")} description={t("loyalty.settings.description")}>
        <ErrorState text={t("common.loadError")} />
      </Section>
    );
  }

  const resetButton = canReset && (
    <Button variant="glassDanger" isLoading={isResetting} onClick={() => setIsResetConfirmOpen(true)}>
      {t("common.reset")}
    </Button>
  );

  return (
    <form onSubmit={(event) => void handleSubmit(event)}>
      <Section
        icon={BadgePercent}
        title={t("loyalty.settings.title")}
        description={t("loyalty.settings.description")}
        aside={
          <>
            <LoyaltyGuideDialog />
            {saved !== null && (
              <StatusPill tone={saved.enabled ? "success" : "warning"}>
                {saved.enabled ? t("loyalty.settings.status.enabled") : t("loyalty.settings.status.disabled")}
              </StatusPill>
            )}
          </>
        }
        footer={
          canManage ? (
            <SaveFooter dirty={dirty} saving={isSaving} disabled={hasInvalid} beside={resetButton} />
          ) : (
            resetButton && <div className="mt-4 flex items-center gap-3">{resetButton}</div>
          )
        }
      >
        <SectionRows>
          <Row icon={Power} label={t("loyalty.settings.enabledLabel")}>
            <Switch checked={enabled} onChange={setEnabled} disabled={isLocked} />
          </Row>
          <div className={`transition-opacity ${enabled ? "" : "opacity-45"}`}>
            <Row icon={CalendarDays} label={t("loyalty.settings.windowLabel")}>
              <PillTabs
                items={windowOptions.map((option) => ({ key: String(option.value), label: option.label }))}
                activeKey={String(windowMonths)}
                onSelect={(key) => setWindowMonths(Number(key))}
                disabled={areSettingsLocked}
              />
            </Row>
          </div>
        </SectionRows>

        <div className={`transition-opacity ${enabled ? "" : "opacity-45"}`}>
          <div className="mt-2 overflow-x-auto pt-3">
            <div className="min-w-[40rem]">
              <div className={`${TIER_ROW_CLASS} mb-1 border-b border-border px-3.5 pb-2.5`}>
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
              <SectionRows flush>
                {tiers.map((tier, index) => {
                  const isDisabled = areSettingsLocked;
                  return (
                    <div
                      key={index}
                      className={`${TIER_ROW_CLASS} min-h-15 rounded-full px-3.5 transition-colors ${isDisabled ? "" : "hover:bg-white/[0.04]"}`}
                    >
                      <IconCircle glyph={<span className="text-[13px] font-semibold">{index + 1}</span>} />
                      <Input
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
                      <Input
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
                      <IconButton
                        size="8"
                        tone="danger"
                        disabled={areSettingsLocked}
                        onClick={() => setTiers((prev) => prev.filter((_, i) => i !== index))}
                      >
                        <Trash2 className="size-4" />
                      </IconButton>
                    </div>
                  );
                })}
                {canManage && tiers.length < MAX_TIERS && (
                  <Row
                    icon={Plus}
                    label={t("loyalty.settings.addTier")}
                    onClick={areSettingsLocked ? undefined : addTier}
                  />
                )}
              </SectionRows>
            </div>
          </div>
          {showTiersError && needsTier && (
            <p className="mt-2 px-3.5 text-[12px] text-error">{t("loyalty.settings.tiersRequired")}</p>
          )}
        </div>
      </Section>

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
