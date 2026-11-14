import {
  CalendarDays,
  Coins,
  CreditCard,
  Flag,
  Gift,
  Hash,
  Info,
  ListOrdered,
  Percent,
  Power,
  Repeat,
  Share2,
} from "lucide-react";
import { useState, type ComponentType, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import {
  getReferralSettings,
  resetReferralSettings,
  type ReferralAccrualStrategy,
  type ReferralLevel,
  type ReferralRewardAmounts,
  type ReferralRewardStrategy,
  type ReferralRewardType,
  type ReferralSettings,
  updateReferralSettings,
} from "@entities/referrals/api";
import { usePermissions } from "@entities/user/use-current-user";
import { getErrorMessage } from "@shared/api/http";
import { currencySymbol } from "@shared/lib/format";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { blockNonIntegerKeys } from "@shared/lib/number-input";
import { Button } from "@shared/ui/Button";
import { GLASS_INNER_CARD_CLASS } from "@shared/ui/classes";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { FieldHint } from "@shared/ui/FieldHint";
import { ErrorState } from "@shared/ui/glass/EmptyState";
import { Field } from "@shared/ui/glass/Field";
import { IconCircle } from "@shared/ui/glass/IconCircle";
import { Input } from "@shared/ui/glass/Input";
import { Row } from "@shared/ui/glass/Row";
import { Section, SectionRows } from "@shared/ui/glass/Section";
import { StatusPill } from "@shared/ui/glass/StatusPill";
import { Switch } from "@shared/ui/glass/Switch";
import { PillTabs } from "@shared/ui/PillTabs";
import { Pressable } from "@shared/ui/Pressable";
import { SaveFooter } from "@shared/ui/SaveFooter";
import { Spinner } from "@shared/ui/Spinner";

const INNER_CARD_CLASS = `flex flex-col gap-3 p-3.5 ${GLASS_INNER_CARD_CLASS}`;
const SWITCH_LABEL_CLASS = "flex items-center gap-1.5 text-sm font-medium text-foreground";

type IconType = ComponentType<{ className?: string }>;

const LEVELS: ReferralLevel[] = [1, 2, 3];
const MAX_PERCENT = 100;
const MAX_INVITEE_REWARD = 3650;
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
  const grid = (
    <div className="grid gap-2 sm:grid-cols-2">
      {options.map(({ value: option, icon }) => {
        const isActive = option === value;
        return (
          <Pressable
            key={option}
            type="button"
            disabled={disabled}
            onClick={() => onChange(option)}
            className={`flex items-start gap-3 rounded-xl border p-3 text-left transition-colors disabled:cursor-not-allowed ${
              isActive ? "border-primary/45 bg-primary/[0.07]" : "border-white/[0.08] bg-white/[0.03] enabled:hover:bg-white/[0.06]"
            }`}
          >
            <IconCircle icon={icon} />
            <div className="flex min-w-0 flex-col gap-0.5">
              <span className="text-sm font-medium text-foreground">{name(option)}</span>
              <span className="text-xs leading-snug text-muted-foreground">{describe(option)}</span>
            </div>
          </Pressable>
        );
      })}
    </div>
  );
  return label ? <Field label={label}>{grid}</Field> : grid;
}

export function ReferralSettingsPage() {
  const { t } = useTranslation();
  const [isSaving, setIsSaving] = useState(false);
  const [isResetConfirmOpen, setIsResetConfirmOpen] = useState(false);
  const [isResetting, setIsResetting] = useState(false);

  const [enabled, setEnabled] = useState(false);
  // the status and the unsaved mark compare with what's stored
  const [saved, setSaved] = useState<ReferralSettings | null>(null);
  const [maxLevel, setMaxLevel] = useState(1);
  const [accrualStrategy, setAccrualStrategy] = useState<ReferralAccrualStrategy>("FIRST_PAYMENT");
  const [rewardType, setRewardType] = useState<ReferralRewardType>("EXTRA_DAYS");
  const [rewardStrategy, setRewardStrategy] = useState<ReferralRewardStrategy>("AMOUNT");
  const [rewardAmounts, setRewardAmounts] = useState<ReferralRewardAmounts>({ 1: "", 2: "", 3: "" });
  const [daysRequirePaid, setDaysRequirePaid] = useState(true);
  const [unlimitedRewardDays, setUnlimitedRewardDays] = useState("365");
  const [inviteeRewardType, setInviteeRewardType] = useState<ReferralRewardType>("EXTRA_DAYS");
  const [inviteeRewardAmount, setInviteeRewardAmount] = useState("0");
  const [inviteeEnabled, setInviteeEnabled] = useState(false);
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
    setSaved(settings);
    setMaxLevel(settings.max_level);
    setAccrualStrategy(settings.accrual_strategy);
    setRewardType(settings.reward_type);
    setRewardStrategy(settings.reward_strategy);
    setRewardAmounts(settings.reward_amounts);
    setDaysRequirePaid(settings.days_require_paid_subscription);
    setUnlimitedRewardDays(String(settings.unlimited_reward_days));
    setInviteeRewardType(settings.invitee_reward_type);
    setInviteeRewardAmount(String(settings.invitee_reward_amount));
    setInviteeEnabled(settings.invitee_reward_amount > 0);
    setAnchorCurrency(settings.anchor_currency);
  };

  const [state] = useAsyncResource(getReferralSettings, { onSuccess: applySettings });

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setIsSaving(true);
    try {
      const updated = await updateReferralSettings({
        enabled,
        max_level: maxLevel,
        accrual_strategy: accrualStrategy,
        reward_type: rewardType,
        reward_strategy: rewardStrategy,
        reward_amounts: amountsToSave(),
        days_require_paid_subscription: daysRequirePaid,
        unlimited_reward_days: Number(unlimitedRewardDays),
        invitee_reward_type: inviteeRewardType,
        invitee_reward_amount: inviteeEnabled ? Number(inviteeRewardAmount) || 0 : 0,
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
      <Section
        icon={Share2}
        title={t("referrals.settings.programTitle")}
        description={t("referrals.settings.programDescription")}
      >
        <ErrorState text={t("common.loadError")} />
      </Section>
    );
  }

  const isPercent = rewardStrategy === "PERCENT";
  const rewardUnit = (amount: number) => t(`referrals.units.${rewardType}`, { count: amount });
  // mirrors the backend: percent of the example base, rounded down, at least 1
  const rewardFor = (level: ReferralLevel): number => {
    const value = Number(rewardAmounts[level]) || 0;
    if (!isPercent || value <= 0) return value;
    return Math.max(1, Math.floor(((Number(exampleBase[rewardType]) || 0) * value) / 100));
  };
  const activeLevels = LEVELS.filter((level) => level <= maxLevel);
  const isAmountInvalid = (level: ReferralLevel) => {
    const value = Number(rewardAmounts[level]);
    return !Number.isInteger(value) || value < 1 || (isPercent && value > MAX_PERCENT);
  };
  const isLevelInvalid = (level: ReferralLevel) => enabled && isAmountInvalid(level);
  const hasInvalidLevel = activeLevels.some(isLevelInvalid);
  // a field locked or hidden by now can't be fixed, so it goes back to what's stored
  const amountsToSave = () => {
    const amounts = { ...rewardAmounts };
    for (const level of LEVELS) {
      if (saved !== null && isAmountInvalid(level)) amounts[level] = saved.reward_amounts[level];
    }
    return amounts;
  };
  // mirrors the backend: a whole number of 1..MAX_INVITEE_REWARD, 0 when switched off
  const isUnlimitedDaysInvalid =
    !/^\d+$/.test(unlimitedRewardDays) || Number(unlimitedRewardDays) < 1 || Number(unlimitedRewardDays) > MAX_INVITEE_REWARD;
  const isInviteeInvalid =
    inviteeEnabled &&
    (!/^\d+$/.test(inviteeRewardAmount) || Number(inviteeRewardAmount) < 1 || Number(inviteeRewardAmount) > MAX_INVITEE_REWARD);
  const dimmed = enabled ? "" : "opacity-45";
  const savedInviteeAmount = saved?.invitee_reward_amount ?? 0;
  const dirty =
    saved !== null &&
    (enabled !== saved.enabled ||
      maxLevel !== saved.max_level ||
      accrualStrategy !== saved.accrual_strategy ||
      rewardType !== saved.reward_type ||
      rewardStrategy !== saved.reward_strategy ||
      activeLevels.some((level) => rewardAmounts[level] !== saved.reward_amounts[level]) ||
      daysRequirePaid !== saved.days_require_paid_subscription ||
      unlimitedRewardDays !== String(saved.unlimited_reward_days) ||
      inviteeEnabled !== savedInviteeAmount > 0 ||
      (inviteeEnabled &&
        (inviteeRewardType !== saved.invitee_reward_type || inviteeRewardAmount !== String(savedInviteeAmount))));
  const resetButton = canReset && (
    <Button variant="glassDanger" isLoading={isResetting} onClick={() => setIsResetConfirmOpen(true)}>
      {t("common.reset")}
    </Button>
  );

  return (
    <form onSubmit={(event) => void handleSubmit(event)} className="grid items-stretch gap-5 lg:grid-cols-2">
      <Section
        stretched
        icon={Share2}
        title={t("referrals.settings.programTitle")}
        description={t("referrals.settings.programDescription")}
        aside={
          saved !== null && (
            <StatusPill tone={saved.enabled ? "success" : "warning"}>
              {saved.enabled ? t("referrals.settings.status.enabled") : t("referrals.settings.status.disabled")}
            </StatusPill>
          )
        }
        footer={
          canManage ? (
            <SaveFooter
              dirty={dirty}
              saving={isSaving}
              disabled={hasInvalidLevel || isInviteeInvalid || isUnlimitedDaysInvalid}
              beside={resetButton}
            />
          ) : (
            resetButton && <div className="mt-4 flex items-center gap-3">{resetButton}</div>
          )
        }
      >
        <SectionRows>
          <Row icon={Power} label={t("referrals.settings.enabledLabel")} hint={t("referrals.settings.enabledHint")}>
            <Switch checked={enabled} onChange={setEnabled} disabled={isLocked} />
          </Row>
        </SectionRows>

        <div className="mt-2 flex flex-1 flex-col gap-3">
          <div className={`flex flex-1 flex-col gap-3 transition-opacity ${dimmed}`}>
            <div className={INNER_CARD_CLASS}>
              <OptionGroup
                label={t("referrals.settings.accrualLabel")}
                value={accrualStrategy}
                options={ACCRUAL_OPTIONS}
                onChange={setAccrualStrategy}
                disabled={areSettingsLocked}
                name={(value) => t(`referrals.settings.accrual.${value}`)}
                describe={(value) => t(`referrals.settings.accrualDescription.${value}`)}
              />
            </div>
            <div className={INNER_CARD_CLASS}>
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
                <div className="flex items-center justify-between gap-3">
                  <span className={SWITCH_LABEL_CLASS}>
                    {t("referrals.settings.daysRequirePaidLabel")}
                    <FieldHint text={t("referrals.settings.daysRequirePaidHint")} />
                  </span>
                  <Switch checked={daysRequirePaid} onChange={setDaysRequirePaid} disabled={areSettingsLocked} />
                </div>
              )}
            </div>
            <div className={INNER_CARD_CLASS}>
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
              {rewardType === "EXTRA_DAYS" && rewardStrategy === "PERCENT" && (
                <div className="flex items-center justify-between gap-3">
                  <label htmlFor="referrals-unlimited-days" className={SWITCH_LABEL_CLASS}>
                    {t("referrals.settings.unlimitedRewardDaysLabel")}
                    <FieldHint text={t("referrals.settings.unlimitedRewardDaysHint")} />
                  </label>
                  <Input
                    className="w-28 shrink-0"
                    id="referrals-unlimited-days"
                    type="number"
                    onKeyDown={blockNonIntegerKeys}
                    min={1}
                    max={MAX_INVITEE_REWARD}
                    step="1"
                    value={unlimitedRewardDays}
                    disabled={areSettingsLocked}
                    onChange={(event) => setUnlimitedRewardDays(event.target.value)}
                    aria-invalid={isUnlimitedDaysInvalid}
                    suffix={t("referrals.units.EXTRA_DAYS", { count: Number(unlimitedRewardDays) || 0 })}
                  />
                </div>
              )}
            </div>
          </div>
        </div>
      </Section>

      <Section
        stretched
        className={`transition-opacity ${dimmed}`}
        icon={ListOrdered}
        title={t("referrals.settings.levelsTitle")}
        description={t("referrals.settings.levelsDescription")}
      >
        <div className="mt-4 flex flex-col gap-3">
          <div className={INNER_CARD_CLASS}>
            <div className="flex items-center justify-between gap-3">
              <span className={SWITCH_LABEL_CLASS}>{t("referrals.settings.maxLevelLabel")}</span>
              <div className="w-32 shrink-0">
                <PillTabs
                  items={LEVELS.map((level) => ({ key: String(level), label: String(level) }))}
                  activeKey={String(maxLevel)}
                  onSelect={(key) => setMaxLevel(Number(key))}
                  disabled={areSettingsLocked}
                />
              </div>
            </div>
          </div>

          <div className="flex flex-col">
            <div className="flex items-center gap-3 rounded-2xl border border-primary/20 bg-primary/[0.07] p-3.5">
              <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-primary/15 text-primary">
                <CreditCard className="size-4" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-foreground">{t("referrals.settings.preview.trigger")}</p>
                <p className="text-xs text-accent-foreground">
                  {t(
                    `referrals.settings.preview.triggerText.${accrualStrategy}.${isPercent ? (`PERCENT_${rewardType}` as const) : "AMOUNT"}`,
                  )}
                </p>
              </div>
              {isPercent && (
                <div className="flex shrink-0 flex-col gap-1">
                  <label htmlFor="referrals-example" className="text-center text-xs text-muted-foreground">
                    {t("referrals.settings.exampleLabel")}
                  </label>
                  <Input
                    className="w-28 shrink-0"
                    id="referrals-example"
                    type="number"
                    onKeyDown={blockNonIntegerKeys}
                    min={0}
                    step="1"
                    value={exampleBase[rewardType]}
                    disabled={!enabled}
                    onChange={(event) => setExampleBase((prev) => ({ ...prev, [rewardType]: event.target.value }))}
                    suffix={
                      rewardType === "POINTS"
                        ? anchorCurrency && currencySymbol(anchorCurrency)
                        : t("referrals.units.EXTRA_DAYS", { count: Number(exampleBase.EXTRA_DAYS) || 0 })
                    }
                  />
                </div>
              )}
            </div>

            {activeLevels.map((level) => {
              const reward = rewardFor(level);
              return (
                <div key={level} className="flex flex-col">
                  <div className="ml-[29px] h-3.5 w-0.5 bg-white/[0.12]" />
                  <div className={`${GLASS_INNER_CARD_CLASS} flex items-center gap-3 p-3.5`}>
                    <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-primary/30 bg-accent text-sm font-semibold text-primary">
                      {level}
                    </div>
                    <label htmlFor={`referrals-reward-${level}`} className="min-w-0 flex-1">
                      <span className="block text-sm font-medium text-foreground">
                        {t(`referrals.settings.preview.who.${level}`)}
                      </span>
                      <span className="block text-xs text-muted-foreground">
                        {t("referrals.settings.levelGets")}{" "}
                        <span className="font-medium text-primary">
                          +{reward} {rewardUnit(reward)}
                        </span>
                      </span>
                    </label>
                    <Input
                      className="w-28 shrink-0"
                      id={`referrals-reward-${level}`}
                      type="number"
                      onKeyDown={blockNonIntegerKeys}
                      min={1}
                      max={isPercent ? MAX_PERCENT : undefined}
                      step="1"
                      value={rewardAmounts[level]}
                      disabled={areSettingsLocked}
                      onChange={(event) =>
                        setRewardAmounts((prev) => ({ ...prev, [level]: event.target.value }))
                      }
                      aria-invalid={isLevelInvalid(level)}
                      suffix={isPercent ? t("referrals.settings.percentUnit") : rewardUnit(Number(rewardAmounts[level]) || 0)}
                    />
                  </div>
                </div>
              );
            })}
          </div>

          {maxLevel < LEVELS.length && (
            <div className="flex gap-2.5 rounded-2xl border border-dashed border-white/[0.12] p-3.5">
              <Info className="mt-px size-4 shrink-0 text-muted-foreground" />
              <p className="text-xs leading-relaxed text-muted-foreground">
                {t("referrals.settings.levelsUnusedNote", { count: maxLevel })}
              </p>
            </div>
          )}

          <div className="flex flex-col gap-3 rounded-2xl border border-primary/20 bg-primary/[0.05] p-3.5">
            <div className="flex items-center justify-between gap-3">
              <span className="flex items-center gap-2 text-sm font-medium text-foreground">
                <Gift className="size-4 text-primary" />
                {t("referrals.settings.invitee.title")}
              </span>
              <Switch
                checked={inviteeEnabled}
                onChange={(next) => {
                  setInviteeEnabled(next);
                  if (next && Number(inviteeRewardAmount) <= 0) setInviteeRewardAmount("1");
                }}
                disabled={areSettingsLocked}
              />
            </div>
            {inviteeEnabled && (
              <>
                <OptionGroup
                  value={inviteeRewardType}
                  options={REWARD_TYPE_OPTIONS}
                  onChange={setInviteeRewardType}
                  disabled={areSettingsLocked}
                  name={(value) => t(`referrals.settings.rewardType.${value}`)}
                  describe={(value) => t(`referrals.settings.invitee.description.${value}`)}
                />
                <div className="flex items-center justify-between gap-3">
                  <label htmlFor="referrals-invitee" className={SWITCH_LABEL_CLASS}>
                    {t("referrals.settings.invitee.amountLabel")}
                    <FieldHint text={t("referrals.settings.invitee.hint")} />
                  </label>
                  <Input
                    className="w-28 shrink-0"
                    id="referrals-invitee"
                    type="number"
                    onKeyDown={blockNonIntegerKeys}
                    min={1}
                    max={MAX_INVITEE_REWARD}
                    step="1"
                    value={inviteeRewardAmount}
                    disabled={areSettingsLocked}
                    onChange={(event) => setInviteeRewardAmount(event.target.value)}
                    aria-invalid={isInviteeInvalid}
                    suffix={t(`referrals.units.${inviteeRewardType}`, { count: Number(inviteeRewardAmount) || 0 })}
                  />
                </div>
                {inviteeRewardType === "POINTS" && (
                  <p className="text-xs text-warning">{t("referrals.settings.invitee.pointsWarning")}</p>
                )}
              </>
            )}
          </div>
        </div>
      </Section>

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
