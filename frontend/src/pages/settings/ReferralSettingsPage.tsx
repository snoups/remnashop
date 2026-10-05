import {
  CalendarDays,
  Coins,
  CreditCard,
  Flag,
  Gift,
  Hash,
  Info,
  Layers,
  Percent,
  Repeat,
  Users,
} from "lucide-react";
import { motion } from "motion/react";
import { useState, type ComponentType, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import {
  getReferralSettings,
  resetReferralSettings,
  type ReferralAccrualStrategy,
  type ReferralRewardStrategy,
  type ReferralRewardType,
  type ReferralSettings,
  updateReferralSettings,
} from "@entities/referrals/api";
import { usePermissions } from "@entities/user/use-current-user";
import { getErrorMessage } from "@shared/api/http";
import { currencySymbol } from "@shared/lib/format";
import { bounceTap } from "@shared/lib/bounceState";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { blockNonIntegerKeys } from "@shared/lib/number-input";
import { ErrorState } from "@shared/ui/EmptyState";
import { SegmentedPills } from "@shared/ui/SegmentedPills";
import { Spinner } from "@shared/ui/Spinner";
import { FieldHint } from "@shared/ui/FieldHint";
import { Switch } from "@shared/ui/Switch";
import { Button } from "@shared/ui/Button";
import { Card } from "@shared/ui/Card";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { EYEBROW_CLASS } from "@shared/ui/classes";
import { CardHeader } from "@shared/ui/CardHeader";

type IconType = ComponentType<{ className?: string }>;

const LEVELS = [1, 2, 3] as const;
const MAX_PERCENT = 100;
const MAX_INVITEE_REWARD = 3650;
// a level without a stored reward starts at the smallest allowed one
const MIN_REWARD = "1";
// the worked example under PERCENT starts from: a payment in the base currency, a term in days
const DEFAULT_EXAMPLE_BASE: Record<ReferralRewardType, string> = { POINTS: "100", EXTRA_DAYS: "30" };

const ACCRUAL_OPTIONS: { value: ReferralAccrualStrategy; icon: IconType }[] = [
  { value: "FIRST_PAYMENT", icon: Flag },
  { value: "EVERY_PAYMENT", icon: Repeat },
];
const REWARD_TYPE_OPTIONS: { value: ReferralRewardType; icon: IconType }[] = [
  { value: "EXTRA_DAYS", icon: CalendarDays },
  { value: "POINTS", icon: Coins },
];
const REWARD_STRATEGY_OPTIONS: { value: ReferralRewardStrategy; icon: IconType }[] = [
  { value: "AMOUNT", icon: Hash },
  { value: "PERCENT", icon: Percent },
];

function OptionGroup<T extends string>({
  label,
  value,
  options,
  onChange,
  disabled,
  describe,
  name,
}: {
  label?: string;
  value: T;
  options: { value: T; icon: IconType }[];
  onChange: (value: T) => void;
  disabled: boolean;
  describe: (value: T) => string;
  name: (value: T) => string;
}) {
  return (
    <div className="flex flex-col gap-2">
      {label && <span className={EYEBROW_CLASS}>{label}</span>}
      <div className="grid gap-2 sm:grid-cols-2">
        {options.map(({ value: option, icon: Icon }) => {
          const isActive = option === value;
          return (
            <motion.button
              key={option}
              type="button"
              disabled={disabled}
              onClick={() => onChange(option)}
              {...(!disabled && bounceTap())}
              className={`flex items-start gap-2.5 rounded-[14px] border p-3 text-left transition-colors disabled:cursor-not-allowed ${
                isActive
                  ? "border-primary/45 bg-primary/[0.07]"
                  : "border-white/[0.08] bg-white/[0.02] enabled:hover:bg-white/[0.04]"
              }`}
            >
              <div
                className={`flex size-[30px] shrink-0 items-center justify-center rounded-full transition-colors ${
                  isActive ? "bg-primary/15 text-primary" : "bg-white/[0.06] text-foreground"
                }`}
              >
                <Icon className="size-[15px]" />
              </div>
              <div className="flex min-w-0 flex-col gap-0.5">
                <span className="text-[13.5px] font-semibold text-foreground">{name(option)}</span>
                <span className="text-xs leading-snug text-muted-foreground">{describe(option)}</span>
              </div>
            </motion.button>
          );
        })}
      </div>
    </div>
  );
}

export function ReferralSettingsPage() {
  const { t } = useTranslation();
  const [isSaving, setIsSaving] = useState(false);
  const [isResetConfirmOpen, setIsResetConfirmOpen] = useState(false);
  const [isResetting, setIsResetting] = useState(false);

  const [enabled, setEnabled] = useState(false);
  // the badge shows what's stored, not the unsaved toggle
  const [savedEnabled, setSavedEnabled] = useState(false);
  const [maxLevel, setMaxLevel] = useState(1);
  const [accrualStrategy, setAccrualStrategy] = useState<ReferralAccrualStrategy>("FIRST_PAYMENT");
  const [rewardType, setRewardType] = useState<ReferralRewardType>("EXTRA_DAYS");
  const [rewardStrategy, setRewardStrategy] = useState<ReferralRewardStrategy>("AMOUNT");
  const [rewardAmounts, setRewardAmounts] = useState<Record<string, string>>({});
  const [daysRequirePaid, setDaysRequirePaid] = useState(true);
  const [inviteeRewardType, setInviteeRewardType] = useState<ReferralRewardType>("EXTRA_DAYS");
  const [inviteeRewardAmount, setInviteeRewardAmount] = useState("0");
  const [anchorCurrency, setAnchorCurrency] = useState<string | null>(null);
  const [exampleBase, setExampleBase] = useState(DEFAULT_EXAMPLE_BASE);

  const permissions = usePermissions();
  const canManage = permissions.includes("REFERRALS_SETTINGS_MANAGE");
  const canReset = permissions.includes("REFERRALS_SETTINGS_RESET");
  const isLocked = !canManage || isSaving;
  // a disabled program's settings stay as they are until it's switched back on
  const areSettingsLocked = isLocked || !enabled;

  const applySettings = (settings: ReferralSettings) => {
    setEnabled(settings.enabled);
    setSavedEnabled(settings.enabled);
    setMaxLevel(settings.max_level);
    setAccrualStrategy(settings.accrual_strategy);
    setRewardType(settings.reward_type);
    setRewardStrategy(settings.reward_strategy);
    setRewardAmounts(settings.reward_amounts);
    setDaysRequirePaid(settings.days_require_paid_subscription);
    setInviteeRewardType(settings.invitee_reward_type);
    setInviteeRewardAmount(String(settings.invitee_reward_amount));
    setAnchorCurrency(settings.anchor_currency);
  };

  const [state] = useAsyncResource(getReferralSettings, { onSuccess: applySettings });

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setIsSaving(true);
    try {
      const amounts: Record<string, string> = {};
      for (let level = 1; level <= maxLevel; level++) {
        amounts[String(level)] = rewardAmounts[String(level)] ?? MIN_REWARD;
      }
      const updated = await updateReferralSettings({
        enabled,
        max_level: maxLevel,
        accrual_strategy: accrualStrategy,
        reward_type: rewardType,
        reward_strategy: rewardStrategy,
        reward_amounts: amounts,
        days_require_paid_subscription: daysRequirePaid,
        invitee_reward_type: inviteeRewardType,
        invitee_reward_amount: Number(inviteeRewardAmount) || 0,
      });
      applySettings(updated);
      toast.success(t("referrals.settings.saved"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("referrals.settings.error")));
    } finally {
      setIsSaving(false);
    }
  };

  const handleReset = async () => {
    setIsResetConfirmOpen(false);
    setIsResetting(true);
    try {
      applySettings(await resetReferralSettings());
      toast.success(t("referrals.settings.resetSuccess"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("referrals.settings.resetError")));
    } finally {
      setIsResetting(false);
    }
  };

  if (state.kind === "loading") return <Spinner size="page" />;
  if (state.kind === "error") {
    return (
      <ErrorState text={t("referrals.loadError")} size="page" />
    );
  }

  const isPercent = rewardStrategy === "PERCENT";
  const amountOf = (level: number) => rewardAmounts[String(level)] ?? MIN_REWARD;
  const rewardUnit = (amount: number) => t(`referrals.units.${rewardType}`, { count: amount });
  // mirrors the backend: percent of the example base, rounded down, at least 1
  const rewardFor = (level: number): number => {
    const value = Number(amountOf(level)) || 0;
    if (!isPercent || value <= 0) return value;
    return Math.max(1, Math.floor(((Number(exampleBase[rewardType]) || 0) * value) / 100));
  };
  const activeLevels = LEVELS.filter((level) => level <= maxLevel);
  // mirrors the backend: an enabled program needs a reward of at least 1 on every active level
  const isLevelInvalid = (level: number) => {
    if (!enabled) return false;
    const value = Number(amountOf(level));
    return !(value >= 1) || (isPercent && value > MAX_PERCENT);
  };
  const hasInvalidLevel = activeLevels.some(isLevelInvalid);
  const dimmed = enabled ? "" : "opacity-45";

  return (
    <form
      onSubmit={(event) => void handleSubmit(event)}
      className="grid items-stretch gap-4 lg:grid-cols-2"
    >
      <Card className="flex flex-col">
        <CardHeader
          icon={Users}
          title={t("referrals.settings.programTitle")}
          description={t("referrals.settings.programDescription")}
          aside={
            <span
              className={`flex h-9 shrink-0 items-center rounded-full px-4 text-[13px] font-semibold ${
                savedEnabled ? "bg-success/10 text-success" : "bg-white/[0.05] text-muted-foreground"
              }`}
            >
              {savedEnabled ? t("referrals.settings.status.enabled") : t("referrals.settings.status.disabled")}
            </span>
          }
        />

        <div className="mt-4 flex items-center justify-between gap-3 py-1">
          <span className="flex items-center gap-1.5 text-sm text-foreground/80">
            {t("referrals.settings.enabledLabel")}
            <FieldHint text={t("referrals.settings.enabledHint")} />
          </span>
          <Switch
            checked={enabled}
            onChange={setEnabled}
            disabled={isLocked}
          />
        </div>

        <div className={`mt-3.5 flex flex-1 flex-col gap-4 transition-opacity ${dimmed}`}>
          <OptionGroup
            label={t("referrals.settings.accrualLabel")}
            value={accrualStrategy}
            options={ACCRUAL_OPTIONS}
            onChange={setAccrualStrategy}
            disabled={areSettingsLocked}
            name={(value) => t(`referrals.settings.accrual.${value}`)}
            describe={(value) => t(`referrals.settings.accrualDescription.${value}`)}
          />
          <OptionGroup
            label={t("referrals.settings.rewardTypeLabel")}
            value={rewardType}
            options={REWARD_TYPE_OPTIONS}
            onChange={setRewardType}
            disabled={areSettingsLocked}
            name={(value) => t(`referrals.settings.rewardType.${value}`)}
            describe={(value) => t(`referrals.settings.rewardTypeDescription.${value}`)}
          />
          {rewardType === "EXTRA_DAYS" && (
            <div className="flex items-center justify-between gap-3 py-1">
              <span className="flex items-center gap-1.5 text-sm text-foreground/80">
                {t("referrals.settings.daysRequirePaidLabel")}
                <FieldHint text={t("referrals.settings.daysRequirePaidHint")} />
              </span>
              <Switch checked={daysRequirePaid} onChange={setDaysRequirePaid} disabled={areSettingsLocked} />
            </div>
          )}
          <OptionGroup
            label={t("referrals.settings.rewardStrategyLabel")}
            value={rewardStrategy}
            options={REWARD_STRATEGY_OPTIONS}
            onChange={setRewardStrategy}
            disabled={areSettingsLocked}
            name={(value) => t(`referrals.settings.rewardStrategy.${value}`)}
            describe={(value) =>
              value === "PERCENT"
                ? t(`referrals.settings.rewardStrategyDescription.PERCENT.${rewardType}`)
                : t("referrals.settings.rewardStrategyDescription.AMOUNT")
            }
          />
          <div className="flex flex-col gap-3 rounded-[14px] border border-primary/20 bg-primary/[0.05] p-3.5">
            <span className="flex items-center gap-2 text-[13px] font-semibold text-foreground">
              <Gift className="size-4 text-primary" />
              {t("referrals.settings.invitee.title")}
            </span>
            <OptionGroup
              value={inviteeRewardType}
              options={REWARD_TYPE_OPTIONS}
              onChange={setInviteeRewardType}
              disabled={areSettingsLocked}
              name={(value) => t(`referrals.settings.rewardType.${value}`)}
              describe={(value) => t(`referrals.settings.invitee.description.${value}`)}
            />
            <div className="flex items-center justify-between gap-3">
              <label htmlFor="referrals-invitee" className="flex items-center gap-1.5 text-sm text-foreground/80">
                {t("referrals.settings.invitee.amountLabel")}
                <FieldHint text={t("referrals.settings.invitee.hint")} />
              </label>
              <div className="flex h-9.5 w-28 shrink-0 items-center gap-1.5 rounded-full border border-border bg-input/60 px-3.5 focus-within:border-primary">
                <input
                  id="referrals-invitee"
                  type="number"
                  onKeyDown={blockNonIntegerKeys}
                  min={0}
                  max={MAX_INVITEE_REWARD}
                  step="1"
                  value={inviteeRewardAmount}
                  disabled={areSettingsLocked}
                  onChange={(event) => setInviteeRewardAmount(event.target.value)}
                  className="w-full min-w-0 bg-transparent text-right text-sm font-semibold tabular-nums text-foreground outline-none [appearance:textfield] disabled:cursor-not-allowed [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
                />
                <span className="shrink-0 text-[13px] text-muted-foreground">
                  {t(`referrals.units.${inviteeRewardType}`, { count: Number(inviteeRewardAmount) || 0 })}
                </span>
              </div>
            </div>
          </div>
        </div>

        {(canManage || canReset) && (
          <div className="mt-4 flex items-center gap-2">
            {canManage && (
              <Button variant="accent" className="w-fit" type="submit" disabled={isSaving || hasInvalidLevel}>
                {isSaving ? t("common.saving") : t("common.save")}
              </Button>
            )}
            {canReset && (
              <Button
                variant="outline"
                className="w-fit"
                type="button"
                onClick={() => setIsResetConfirmOpen(true)}
                disabled={isResetting}
              >
                {t("common.reset")}
              </Button>
            )}
          </div>
        )}
      </Card>

      <Card className={`flex flex-col transition-opacity ${dimmed}`}>
        <CardHeader
          icon={Layers}
          title={t("referrals.settings.levelsTitle")}
          description={t("referrals.settings.levelsDescription")}
        />

        <div className="mt-4 flex items-center justify-between gap-3">
          <span className="text-sm text-foreground/80">{t("referrals.settings.maxLevelLabel")}</span>
          <SegmentedPills
            value={maxLevel}
            onChange={setMaxLevel}
            disabled={areSettingsLocked}
            options={LEVELS.map((level) => ({ value: level, label: String(level) }))}
          />
        </div>

        <div className="mt-4 flex flex-col">
          <div className="flex items-center gap-3 rounded-[14px] border border-primary/20 bg-primary/[0.07] p-3">
            <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-primary/15 text-primary">
              <CreditCard className="size-4" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-[13px] font-semibold text-foreground">{t("referrals.settings.preview.trigger")}</p>
              <p className="text-[12px] text-accent-foreground">
                {t(
                  `referrals.settings.preview.triggerText.${accrualStrategy}.${isPercent ? (`PERCENT_${rewardType}` as const) : "AMOUNT"}`,
                )}
              </p>
            </div>
            {isPercent && (
              <div className="flex shrink-0 flex-col gap-1">
                <label htmlFor="referrals-example" className="text-center text-[12px] text-muted-foreground">
                  {t("referrals.settings.exampleLabel")}
                </label>
                <div className="flex h-9.5 w-28 items-center gap-1.5 rounded-full border border-border bg-input/60 px-3.5 focus-within:border-primary">
                  <input
                    id="referrals-example"
                    type="number"
                    onKeyDown={blockNonIntegerKeys}
                    min={0}
                    step="1"
                    value={exampleBase[rewardType]}
                    disabled={!enabled}
                    onChange={(event) => setExampleBase((prev) => ({ ...prev, [rewardType]: event.target.value }))}
                    className="w-full min-w-0 bg-transparent text-right text-sm font-semibold tabular-nums text-foreground outline-none [appearance:textfield] disabled:cursor-not-allowed [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
                  />
                  <span className="shrink-0 text-[13px] text-muted-foreground">
                    {rewardType === "POINTS"
                      ? anchorCurrency && currencySymbol(anchorCurrency)
                      : t("referrals.units.EXTRA_DAYS", { count: Number(exampleBase.EXTRA_DAYS) || 0 })}
                  </span>
                </div>
              </div>
            )}
          </div>

          {activeLevels.map((level) => {
            const reward = rewardFor(level);
            return (
              <div key={level} className="flex flex-col">
                <div className="ml-[27px] h-3.5 w-0.5 bg-white/[0.12]" />
                <div className="flex items-center gap-3 rounded-[14px] bg-white/[0.03] px-3 py-2.5">
                  <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-primary/30 bg-accent text-[13px] font-bold text-primary">
                    {level}
                  </div>
                  <label htmlFor={`referrals-reward-${level}`} className="min-w-0 flex-1">
                    <span className="block text-[13px] font-medium text-foreground">
                      {t(`referrals.settings.preview.who.${level}`)}
                    </span>
                    <span className="block text-[12px] text-muted-foreground">
                      {t("referrals.settings.levelGets")}{" "}
                      <span className="font-semibold text-primary">
                        +{reward} {rewardUnit(reward)}
                      </span>
                    </span>
                  </label>
                  <div className={`flex h-9.5 w-28 shrink-0 items-center gap-1.5 rounded-full border ${isLevelInvalid(level) ? "border-error/60" : "border-border"} bg-input/60 px-3.5 focus-within:border-primary`}>
                    <input
                      id={`referrals-reward-${level}`}
                      type="number"
                      onKeyDown={blockNonIntegerKeys}
                      min={1}
                      max={isPercent ? MAX_PERCENT : undefined}
                      step="1"
                      value={amountOf(level)}
                      disabled={areSettingsLocked}
                      onChange={(event) =>
                        setRewardAmounts((prev) => ({ ...prev, [String(level)]: event.target.value }))
                      }
                      className="w-full min-w-0 bg-transparent text-right text-sm font-semibold tabular-nums text-foreground outline-none [appearance:textfield] disabled:cursor-not-allowed [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
                    />
                    <span className="shrink-0 text-[13px] text-muted-foreground">
                      {isPercent ? t("referrals.settings.percentUnit") : rewardUnit(Number(amountOf(level)) || 0)}
                    </span>
                  </div>
                </div>
              </div>
            );
          })}

          {maxLevel < LEVELS.length && (
            <div className="mt-4 flex gap-2.5 rounded-xl border border-dashed border-white/[0.12] p-3">
              <Info className="mt-px size-4 shrink-0 text-muted-foreground" />
              <p className="text-[12px] leading-relaxed text-muted-foreground">
                {t("referrals.settings.levelsUnusedNote", { count: maxLevel })}
              </p>
            </div>
          )}
        </div>
      </Card>

      {isResetConfirmOpen && (
        <ConfirmDialog
          title={t("referrals.settings.resetConfirmTitle")}
          message={t("referrals.settings.resetConfirmText")}
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
