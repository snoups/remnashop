import { AlertCircle, Filter, Loader2 } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useState, type FormEvent } from "react";
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
import { SelectDropdown } from "@shared/ui/SelectDropdown";
import { Switch } from "@shared/ui/Switch";

type LoadState = { kind: "loading" } | { kind: "error" } | { kind: "ready" };

const MAX_LEVELS = [1, 2, 3];
const ACCRUAL_STRATEGIES: ReferralAccrualStrategy[] = ["FIRST_PAYMENT", "EVERY_PAYMENT"];
const REWARD_TYPES: ReferralRewardType[] = ["EXTRA_DAYS", "POINTS"];

const fieldClassName =
  "rounded-xl border border-border bg-input/60 px-3 py-2 text-sm text-foreground outline-none focus:border-primary";

export function ReferralsPage() {
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
        amounts[String(level)] = rewardAmounts[String(level)] ?? "0";
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

  return (
    <div className="flex flex-col gap-4">
      <div className="relative rounded-2xl border border-white/[0.08] bg-white/[0.03] p-4">
        {state.kind === "loading" && (
          <div className="flex flex-col items-center gap-2 py-12 text-muted-foreground">
            <Loader2 className="size-5 animate-spin" />
            <p className="text-sm">{t("referrals.loading")}</p>
          </div>
        )}
        {state.kind === "error" && (
          <div className="flex flex-col items-center gap-2 py-12 text-error">
            <AlertCircle className="size-5" />
            <p className="text-sm">{t("referrals.loadError")}</p>
          </div>
        )}
        {state.kind === "ready" && (
          <form onSubmit={(event) => void handleSubmit(event)} className="flex flex-col gap-4">
            <label className="flex items-center gap-2.5 text-sm font-medium text-foreground/80">
              <Switch checked={enabled} onChange={setEnabled} ariaLabel={t("referrals.settings.enabledLabel")} />
              {t("referrals.settings.enabledLabel")}
            </label>

            <div className="flex gap-3">
              <div className="flex flex-1 flex-col gap-1">
                <span className="text-sm font-medium text-foreground/80">{t("referrals.settings.maxLevelLabel")}</span>
                <SelectDropdown
                  id="referrals-max-level"
                  value={String(maxLevel)}
                  onChange={(value) => setMaxLevel(Number(value))}
                  icon={Filter}
                  placeholder={String(maxLevel)}
                  options={MAX_LEVELS.map((level) => ({ value: String(level), label: String(level) }))}
                />
              </div>
              <div className="flex flex-1 flex-col gap-1">
                <span className="text-sm font-medium text-foreground/80">{t("referrals.settings.accrualLabel")}</span>
                <SelectDropdown
                  id="referrals-accrual"
                  value={accrualStrategy}
                  onChange={(value) => setAccrualStrategy(value as ReferralAccrualStrategy)}
                  icon={Filter}
                  placeholder={t(`referrals.settings.accrual.${accrualStrategy}`)}
                  options={ACCRUAL_STRATEGIES.map((value) => ({
                    value,
                    label: t(`referrals.settings.accrual.${value}`),
                  }))}
                />
              </div>
              <div className="flex flex-1 flex-col gap-1">
                <span className="text-sm font-medium text-foreground/80">{t("referrals.settings.rewardTypeLabel")}</span>
                <SelectDropdown
                  id="referrals-reward-type"
                  value={rewardType}
                  onChange={(value) => setRewardType(value as ReferralRewardType)}
                  icon={Filter}
                  placeholder={t(`referrals.settings.rewardType.${rewardType}`)}
                  options={REWARD_TYPES.map((value) => ({
                    value,
                    label: t(`referrals.settings.rewardType.${value}`),
                  }))}
                />
              </div>
            </div>

            <div className="flex gap-3">
              {Array.from({ length: maxLevel }, (_, index) => index + 1).map((level) => (
                <div key={level} className="flex flex-1 flex-col gap-1">
                  <label htmlFor={`referrals-reward-${level}`} className="text-sm font-medium text-foreground/80">
                    {t("referrals.settings.levelRewardLabel", { level })}
                  </label>
                  <input
                    id={`referrals-reward-${level}`}
                    type="number"
                    min={0}
                    step="0.01"
                    value={rewardAmounts[String(level)] ?? "0"}
                    onChange={(event) =>
                      setRewardAmounts((prev) => ({ ...prev, [String(level)]: event.target.value }))
                    }
                    className={fieldClassName}
                  />
                </div>
              ))}
            </div>

            {canManage && (
              <div className="flex justify-end">
                <motion.button
                  type="submit"
                  disabled={isSaving}
                  {...bounceTap(bounceStrength)}
                  className="flex items-center gap-1.5 rounded-full bg-accent px-4 py-2 text-[13px] font-semibold text-primary transition-colors hover:bg-primary/20 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {isSaving ? t("referrals.settings.saving") : t("referrals.settings.save")}
                </motion.button>
              </div>
            )}
          </form>
        )}
      </div>
    </div>
  );
}
