import { AlertCircle, CreditCard, Gift, Info, Layers, Power, Repeat, User, Users } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useState, type ComponentType, type FormEvent, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import {
  getReferralSettings,
  type ReferralAccrualStrategy,
  type ReferralRewardType,
  type ReferralSettings,
  updateReferralSettings,
} from "@entities/referrals/api";
import { useCurrentUser } from "@entities/user/use-current-user";
import { getErrorMessage } from "@shared/api/http";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { toast } from "@shared/lib/toast";
import { SegmentedPills } from "@shared/ui/SegmentedPills";
import { Spinner } from "@shared/ui/Spinner";
import { Switch } from "@shared/ui/Switch";

type LoadState = { kind: "loading" } | { kind: "error" } | { kind: "ready" };

const LEVELS = [1, 2, 3];
const ACCRUAL_STRATEGIES: ReferralAccrualStrategy[] = ["FIRST_PAYMENT", "EVERY_PAYMENT"];
const REWARD_TYPES: ReferralRewardType[] = ["EXTRA_DAYS", "POINTS"];

const cardClassName = "rounded-2xl border border-white/[0.08] bg-white/[0.03] p-4";
const rowIconClassName =
  "flex size-8 shrink-0 items-center justify-center rounded-full bg-white/[0.06] text-foreground";

function CardHeader({
  icon: Icon,
  title,
  description,
  children,
}: {
  icon: ComponentType<{ className?: string }>;
  title: string;
  description: string;
  children?: ReactNode;
}) {
  return (
    <>
      <div className="flex items-center gap-2.5">
        <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] text-foreground backdrop-blur-md">
          <Icon className="size-4" />
        </div>
        <div className="min-w-0 flex-1">
          <h2 className="text-sm font-bold text-foreground">{title}</h2>
          <p className="mt-0.5 text-[12.5px] text-muted-foreground">{description}</p>
        </div>
        {children}
      </div>
      <div className="-mx-4 mt-4 border-t border-white/[0.07]" />
    </>
  );
}

function SettingRow({
  icon: Icon,
  label,
  description,
  children,
}: {
  icon: ComponentType<{ className?: string }>;
  label: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-full px-[12.5px] py-2.5">
      <div className={rowIconClassName}>
        <Icon className="size-4" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-[13px] font-medium text-foreground">{label}</p>
        <p className="text-[12px] text-muted-foreground">{description}</p>
      </div>
      {children}
    </div>
  );
}

export function ReferralSettingsPage() {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const [state, setState] = useState<LoadState>({ kind: "loading" });
  const [isSaving, setIsSaving] = useState(false);

  const [enabled, setEnabled] = useState(false);
  const [maxLevel, setMaxLevel] = useState(1);
  const [accrualStrategy, setAccrualStrategy] = useState<ReferralAccrualStrategy>("FIRST_PAYMENT");
  const [rewardType, setRewardType] = useState<ReferralRewardType>("EXTRA_DAYS");
  const [rewardAmounts, setRewardAmounts] = useState<Record<string, string>>({});

  const currentUserState = useCurrentUser();
  const permissions =
    currentUserState.kind === "ready" ? currentUserState.data.effective_permissions : [];
  const canManage = permissions.includes("REFERRALS_SETTINGS_MANAGE");
  const isLocked = !canManage || isSaving;

  const applySettings = (settings: ReferralSettings) => {
    setEnabled(settings.enabled);
    setMaxLevel(settings.max_level);
    setAccrualStrategy(settings.accrual_strategy);
    setRewardType(settings.reward_type);
    setRewardAmounts(settings.reward_amounts);
  };

  useEffect(() => {
    const controller = new AbortController();
    getReferralSettings(controller.signal)
      .then((settings) => {
        if (controller.signal.aborted) return;
        applySettings(settings);
        setState({ kind: "ready" });
      })
      .catch(() => {
        if (!controller.signal.aborted) setState({ kind: "error" });
      });
    return () => controller.abort();
  }, []);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setIsSaving(true);
    try {
      const amounts: Record<string, string> = {};
      for (let level = 1; level <= maxLevel; level++) {
        amounts[String(level)] = rewardAmounts[String(level)] || "0";
      }
      const updated = await updateReferralSettings({
        enabled,
        max_level: maxLevel,
        accrual_strategy: accrualStrategy,
        reward_type: rewardType,
        reward_amounts: amounts,
      });
      applySettings(updated);
      toast.success(t("referrals.settings.saved"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("referrals.settings.error")));
    } finally {
      setIsSaving(false);
    }
  };

  if (state.kind === "loading") return <Spinner className="py-12" />;
  if (state.kind === "error") {
    return (
      <div className="flex flex-col items-center gap-2 py-12 text-error">
        <AlertCircle className="size-5" />
        <p className="text-sm">{t("referrals.loadError")}</p>
      </div>
    );
  }

  const amountOf = (level: number) => rewardAmounts[String(level)] ?? "0";
  const unit = (level: number) => t(`referrals.units.${rewardType}`, { count: Number(amountOf(level)) || 0 });
  const dimmed = enabled ? "" : "pointer-events-none opacity-45";

  return (
    <form onSubmit={(event) => void handleSubmit(event)} className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <span
          className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-[12.5px] font-semibold ${
            enabled ? "border-success/30 bg-success/10 text-success" : "border-border bg-white/[0.04] text-muted-foreground"
          }`}
        >
          <span className={`size-1.5 rounded-full ${enabled ? "bg-success" : "bg-muted-foreground"}`} />
          {enabled ? t("referrals.settings.status.enabled") : t("referrals.settings.status.disabled")}
        </span>
        {canManage && (
          <motion.button
            type="submit"
            disabled={isSaving}
            {...bounceTap(bounceStrength)}
            className="rounded-full bg-accent px-4 py-2 text-sm font-medium text-primary transition-colors hover:bg-primary/20 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isSaving ? t("referrals.settings.saving") : t("referrals.settings.save")}
          </motion.button>
        )}
      </div>

      {!enabled && <p className="text-[12.5px] text-warning">{t("referrals.settings.disabledNote")}</p>}

      <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_380px]">
        <div className="flex flex-col gap-4">
          <section className={cardClassName}>
            <CardHeader
              icon={Users}
              title={t("referrals.settings.programTitle")}
              description={t("referrals.settings.programDescription")}
            />
            <div className="mt-2 flex flex-col">
              <SettingRow
                icon={Power}
                label={t("referrals.settings.enabledLabel")}
                description={t("referrals.settings.enabledDescription")}
              >
                <Switch
                  checked={enabled}
                  onChange={setEnabled}
                  disabled={isLocked}
                  ariaLabel={t("referrals.settings.enabledLabel")}
                />
              </SettingRow>
              <div className={`mt-1 flex flex-col gap-1 border-t border-white/[0.08] pt-1 ${dimmed}`}>
                <SettingRow
                  icon={Repeat}
                  label={t("referrals.settings.accrualLabel")}
                  description={t("referrals.settings.accrualDescription")}
                >
                  <SegmentedPills
                    value={accrualStrategy}
                    onChange={setAccrualStrategy}
                    disabled={isLocked}
                    ariaLabel={t("referrals.settings.accrualLabel")}
                    options={ACCRUAL_STRATEGIES.map((value) => ({
                      value,
                      label: t(`referrals.settings.accrual.${value}`),
                    }))}
                  />
                </SettingRow>
                <SettingRow
                  icon={Gift}
                  label={t("referrals.settings.rewardTypeLabel")}
                  description={t(`referrals.settings.rewardTypeDescription.${rewardType}`)}
                >
                  <SegmentedPills
                    value={rewardType}
                    onChange={setRewardType}
                    disabled={isLocked}
                    ariaLabel={t("referrals.settings.rewardTypeLabel")}
                    options={REWARD_TYPES.map((value) => ({
                      value,
                      label: t(`referrals.settings.rewardType.${value}`),
                    }))}
                  />
                </SettingRow>
              </div>
            </div>
          </section>

          <section className={`${cardClassName} ${dimmed}`}>
            <CardHeader
              icon={Layers}
              title={t("referrals.settings.levelsTitle")}
              description={t("referrals.settings.levelsDescription")}
            >
              <SegmentedPills
                value={maxLevel}
                onChange={setMaxLevel}
                disabled={isLocked}
                ariaLabel={t("referrals.settings.maxLevelLabel")}
                options={LEVELS.map((level) => ({ value: level, label: String(level) }))}
              />
            </CardHeader>
            <div className="mt-2 flex flex-col">
              {LEVELS.map((level) => {
                const isActive = level <= maxLevel;
                const isNextActive = level + 1 <= maxLevel;
                return (
                  <div key={level} className={`flex items-stretch gap-3 px-[12.5px] ${isActive ? "" : "opacity-40"}`}>
                    <div className="flex w-8 shrink-0 flex-col items-center">
                      <div
                        className={`h-2.5 w-0.5 ${level === 1 ? "" : isActive ? "bg-primary/30" : "bg-white/10"}`}
                      />
                      <div
                        className={`flex size-8 items-center justify-center rounded-full border text-[13px] font-bold ${
                          isActive
                            ? "border-primary/30 bg-accent text-primary"
                            : "border-dashed border-white/20 bg-white/[0.04] text-muted-foreground"
                        }`}
                      >
                        {level}
                      </div>
                      <div
                        className={`w-0.5 flex-1 ${
                          level === LEVELS.length ? "" : isNextActive ? "bg-primary/30" : "bg-white/10"
                        }`}
                      />
                    </div>
                    <div className="min-w-0 flex-1 py-2.5">
                      <label
                        htmlFor={`referrals-reward-${level}`}
                        className="block text-[13px] font-medium text-foreground"
                      >
                        {t("referrals.settings.levelRewardLabel", { level })}
                      </label>
                      <p className="text-[12px] text-muted-foreground">
                        {isActive
                          ? t(`referrals.settings.levelDescription.${level}`)
                          : t("referrals.settings.levelUnused")}
                      </p>
                    </div>
                    <div className="flex items-center py-2.5">
                      <div className="flex h-9 items-center gap-1.5 rounded-xl border border-border bg-input/60 px-3 focus-within:border-primary">
                        <span className="text-[13px] text-muted-foreground">+</span>
                        <input
                          id={`referrals-reward-${level}`}
                          type="number"
                          min={0}
                          step="1"
                          value={amountOf(level)}
                          disabled={!isActive || isLocked}
                          onChange={(event) =>
                            setRewardAmounts((prev) => ({ ...prev, [String(level)]: event.target.value }))
                          }
                          className="w-14 bg-transparent text-right text-sm font-semibold tabular-nums text-foreground outline-none [appearance:textfield] disabled:cursor-not-allowed [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
                        />
                        <span className="min-w-11 text-[12.5px] text-muted-foreground">{unit(level)}</span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        </div>

        <aside className={`${cardClassName} ${dimmed}`}>
          <CardHeader
            icon={Info}
            title={t("referrals.settings.preview.title")}
            description={t("referrals.settings.preview.description")}
          />
          <div className="mt-4 flex items-center gap-3 rounded-[14px] border border-primary/20 bg-primary/[0.07] p-3">
            <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-primary/15 text-primary">
              <CreditCard className="size-4" />
            </div>
            <div className="min-w-0">
              <p className="text-[13px] font-semibold text-foreground">{t("referrals.settings.preview.trigger")}</p>
              <p className="text-[12px] text-accent-foreground">
                {t(`referrals.settings.preview.triggerText.${accrualStrategy}`)}
              </p>
            </div>
          </div>
          <div className="flex flex-col">
            {LEVELS.filter((level) => level <= maxLevel).map((level) => (
              <div key={level} className="flex flex-col">
                <div className="ml-[27px] h-3.5 w-0.5 bg-white/[0.12]" />
                <div className="flex items-center gap-3 rounded-[14px] bg-white/[0.03] px-3 py-2.5">
                  <div className={rowIconClassName}>
                    <User className="size-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-[13px] font-medium text-foreground">
                      {t(`referrals.settings.preview.who.${level}`)}
                    </p>
                    <p className="text-[12px] text-muted-foreground">{t("referrals.list.level", { level })}</p>
                  </div>
                  <span className="whitespace-nowrap rounded-full bg-accent px-2.5 py-0.5 text-[12.5px] font-bold tabular-nums text-primary">
                    +{amountOf(level) || "0"} {unit(level)}
                  </span>
                </div>
              </div>
            ))}
          </div>
          <div className="mt-4 flex gap-2.5 rounded-xl border border-dashed border-white/[0.12] p-3">
            <Info className="mt-px size-4 shrink-0 text-muted-foreground" />
            <p className="text-[12px] leading-relaxed text-muted-foreground">
              {t(`referrals.settings.preview.footnote.${rewardType}`)}
            </p>
          </div>
        </aside>
      </div>
    </form>
  );
}
