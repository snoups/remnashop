import { Dices, Package, Tag, Ticket, X } from "lucide-react";
import { motion } from "motion/react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import type { AddOnListItem } from "@entities/addons/api";
import type { Plan } from "@entities/plans/api";
import {
  type CreatePromocodeRequest,
  createPromocode,
  generatePromocodeCode,
  type Promocode,
  type PromocodeRewardType,
} from "@entities/promocodes/api";
import {
  describeReward,
  limitsToPayload,
  type PromocodeLimitsDraft,
  type PromocodeReward,
  REWARD_TYPE_ICON,
  REWARD_TYPES,
} from "@entities/promocodes/display";
import {
  PromocodeLimitsFields,
  promocodeFieldClassName,
  promocodeSectionClassName,
  promocodeSectionTitleClassName,
} from "@entities/promocodes/PromocodeLimitsFields";
import { getErrorMessage } from "@shared/api/http";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { parseRequiredInt } from "@shared/lib/number-input";
import { toast } from "@shared/lib/toast";
import { Modal, useModalClose } from "@shared/ui/Modal";
import { SelectDropdown } from "@shared/ui/SelectDropdown";

const DAY_PRESETS = [7, 30, 90];
const labelClassName = "text-sm font-medium text-foreground/80";

interface PromocodeCreateDialogProps {
  canGenerateCode: boolean;
  addons: AddOnListItem[];
  plans: Plan[];
  onClose: () => void;
  onSaved: (promocode: Promocode) => void;
}

export function PromocodeCreateDialog({ onClose, ...props }: PromocodeCreateDialogProps) {
  return (
    <Modal onClose={onClose} size="lg" scrollable>
      <PromocodeCreateDialogBody {...props} />
    </Modal>
  );
}

function PromocodeCreateDialogBody({
  canGenerateCode,
  addons,
  plans,
  onSaved,
}: Omit<PromocodeCreateDialogProps, "onClose">) {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const close = useModalClose();
  const [isSubmitting, setIsSubmitting] = useState(false);

  const [code, setCode] = useState("");
  const [rewardType, setRewardType] = useState<PromocodeRewardType>("DURATION");
  const [rewardDays, setRewardDays] = useState("30");
  const [rewardPercent, setRewardPercent] = useState("10");
  const [rewardAddonId, setRewardAddonId] = useState("");
  const [rewardPlanId, setRewardPlanId] = useState("");
  const [rewardDurationDays, setRewardDurationDays] = useState("30");
  const [limits, setLimits] = useState<PromocodeLimitsDraft>({
    availability: "ALL",
    allowedUserIds: [],
    expiresAt: "",
    maxActivations: "",
    isReusable: false,
  });

  const matchingAddons = addons.filter((addon) => addon.type === rewardType);
  const isDiscount = rewardType === "PERSONAL_DISCOUNT" || rewardType === "PURCHASE_DISCOUNT";

  const draftReward: PromocodeReward = {
    reward_type: rewardType,
    reward: rewardType === "DURATION" ? Number(rewardDays) || 0 : isDiscount ? Number(rewardPercent) || 0 : null,
    reward_addon_id: rewardAddonId ? Number(rewardAddonId) : null,
    reward_plan_id: rewardPlanId ? Number(rewardPlanId) : null,
    reward_duration_days: Number(rewardDurationDays) || 0,
  };

  const handleGenerate = async () => {
    try {
      setCode(await generatePromocodeCode());
    } catch (err) {
      toast.error(getErrorMessage(err, t("promocodes.create.error")));
    }
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();

    const limitsPayload = limitsToPayload(limits);
    if (limitsPayload === undefined) {
      toast.error(t("errors.invalidNumber"));
      return;
    }

    const payload: CreatePromocodeRequest = {
      code: code.trim().toUpperCase(),
      reward_type: rewardType,
      ...limitsPayload,
    };

    if (rewardType === "DURATION") {
      const reward = parseRequiredInt(rewardDays, 1);
      if (reward === undefined) {
        toast.error(t("errors.invalidNumber"));
        return;
      }
      payload.reward = reward;
    } else if (rewardType === "TRAFFIC" || rewardType === "DEVICES") {
      payload.reward_addon_id = rewardAddonId ? Number(rewardAddonId) : null;
    } else if (rewardType === "SUBSCRIPTION") {
      const rewardDurationDaysValue = parseRequiredInt(rewardDurationDays, 1);
      if (rewardDurationDaysValue === undefined) {
        toast.error(t("errors.invalidNumber"));
        return;
      }
      payload.reward_plan_id = rewardPlanId ? Number(rewardPlanId) : null;
      payload.reward_duration_days = rewardDurationDaysValue;
    } else {
      const reward = parseRequiredInt(rewardPercent, 0);
      if (reward === undefined) {
        toast.error(t("errors.invalidNumber"));
        return;
      }
      payload.reward = reward;
    }

    setIsSubmitting(true);
    try {
      const created = await createPromocode(payload);
      toast.success(t("promocodes.create.saved"));
      onSaved(created);
      close();
    } catch (err) {
      toast.error(getErrorMessage(err, t("promocodes.create.error")));
    } finally {
      setIsSubmitting(false);
    }
  };

  const daysSuffix = <span className="pr-3 text-[13px] text-muted-foreground">{t("promocodes.create.daysSuffix")}</span>;

  return (
    <>
      <div className="flex shrink-0 items-center justify-between border-b border-border px-5 py-4">
        <h2 className="flex items-center gap-2.5 text-base font-bold text-foreground">
          <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] text-foreground backdrop-blur-md">
            <Ticket className="size-4" />
          </div>
          {t("promocodes.create.title")}
        </h2>
        <button
          type="button"
          onClick={close}
          aria-label={t("promocodes.create.close")}
          className="flex size-8 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-white/[0.06] hover:text-foreground"
        >
          <X className="size-4" />
        </button>
      </div>

      <form onSubmit={(event) => void handleSubmit(event)} className="flex min-h-0 flex-1 flex-col">
        <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto p-4">
          <section className={promocodeSectionClassName}>
            <label htmlFor="promo-code" className={promocodeSectionTitleClassName}>
              {t("promocodes.sections.code")}
            </label>
            <div className="flex gap-2">
              <input
                id="promo-code"
                value={code}
                onChange={(event) => setCode(event.target.value.toUpperCase())}
                placeholder={t("promocodes.create.codePlaceholder")}
                autoComplete="off"
                className={`${promocodeFieldClassName} min-w-0 flex-1 py-2.5 font-mono text-base font-bold tracking-wider`}
              />
              {canGenerateCode && (
                <motion.button
                  type="button"
                  onClick={() => void handleGenerate()}
                  {...bounceTap(bounceStrength)}
                  className="flex shrink-0 items-center gap-1.5 rounded-full border border-border px-3.5 text-[12.5px] font-medium text-foreground/90 transition-colors hover:bg-white/5"
                >
                  <Dices className="size-3.5" />
                  {t("promocodes.create.generate")}
                </motion.button>
              )}
            </div>
          </section>

          <section className={promocodeSectionClassName}>
            <h3 className={promocodeSectionTitleClassName}>{t("promocodes.sections.reward")}</h3>
            <div role="radiogroup" aria-label={t("promocodes.create.rewardTypeLabel")} className="grid grid-cols-3 gap-2">
              {REWARD_TYPES.map((type) => {
                const Icon = REWARD_TYPE_ICON[type];
                const isSelected = rewardType === type;
                return (
                  <motion.button
                    key={type}
                    type="button"
                    role="radio"
                    aria-checked={isSelected}
                    onClick={() => setRewardType(type)}
                    {...bounceTap(bounceStrength, 0.03)}
                    className={`flex flex-col items-start gap-2 rounded-[14px] border p-3 text-left transition-colors ${
                      isSelected
                        ? "border-primary/50 bg-accent text-primary"
                        : "border-border bg-white/[0.02] text-foreground hover:bg-white/[0.05]"
                    }`}
                  >
                    <Icon className={`size-[18px] ${isSelected ? "" : "text-muted-foreground"}`} />
                    <span className="text-[12.5px] font-semibold">{t(`promocodes.rewardTypeShort.${type}`)}</span>
                  </motion.button>
                );
              })}
            </div>

            {rewardType === "DURATION" && (
              <div className="flex flex-col gap-1">
                <label htmlFor="promo-reward-days" className={labelClassName}>
                  {t("promocodes.create.rewardDaysLabel")}
                </label>
                <div className="flex items-center gap-2">
                  <div className="flex flex-1 items-center rounded-xl border border-border bg-input/60 focus-within:border-primary">
                    <input
                      id="promo-reward-days"
                      type="number"
                      min={1}
                      step="1"
                      value={rewardDays}
                      onChange={(event) => setRewardDays(event.target.value)}
                      className="min-w-0 flex-1 bg-transparent px-3 py-2 text-sm text-foreground outline-none"
                    />
                    {daysSuffix}
                  </div>
                  {DAY_PRESETS.map((days) => (
                    <button
                      key={days}
                      type="button"
                      aria-pressed={rewardDays === String(days)}
                      onClick={() => setRewardDays(String(days))}
                      className={`rounded-full border px-3 py-1.5 text-[12.5px] font-medium transition-colors ${
                        rewardDays === String(days)
                          ? "border-primary/40 bg-accent text-primary"
                          : "border-border text-foreground hover:bg-white/5"
                      }`}
                    >
                      {days}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {isDiscount && (
              <div className="flex flex-col gap-1">
                <label htmlFor="promo-reward-percent" className={labelClassName}>
                  {t("promocodes.create.rewardPercentLabel")}
                </label>
                <input
                  id="promo-reward-percent"
                  type="number"
                  min={0}
                  max={100}
                  step="1"
                  value={rewardPercent}
                  onChange={(event) => setRewardPercent(event.target.value)}
                  className={promocodeFieldClassName}
                />
              </div>
            )}

            {(rewardType === "TRAFFIC" || rewardType === "DEVICES") && (
              <div className="flex flex-col gap-1">
                <span className={labelClassName}>{t("promocodes.create.rewardAddonLabel")}</span>
                {matchingAddons.length === 0 ? (
                  <p className="text-[12.5px] text-muted-foreground">{t("promocodes.create.rewardAddonEmpty")}</p>
                ) : (
                  <SelectDropdown
                    id="promo-reward-addon"
                    value={rewardAddonId}
                    onChange={setRewardAddonId}
                    icon={Package}
                    placeholder={t("promocodes.create.rewardAddonPlaceholder")}
                    options={matchingAddons.map((addon) => ({
                      value: String(addon.id),
                      label: `${addon.name} (${addon.amount})`,
                    }))}
                  />
                )}
              </div>
            )}

            {rewardType === "SUBSCRIPTION" && (
              <div className="grid grid-cols-[minmax(0,3fr)_minmax(0,2fr)] gap-3">
                <div className="flex flex-col gap-1">
                  <span className={labelClassName}>{t("promocodes.create.rewardPlanLabel")}</span>
                  {plans.length === 0 ? (
                    <p className="text-[12.5px] text-muted-foreground">{t("promocodes.create.rewardPlanEmpty")}</p>
                  ) : (
                    <SelectDropdown
                      id="promo-reward-plan"
                      value={rewardPlanId}
                      onChange={setRewardPlanId}
                      icon={Tag}
                      placeholder={t("promocodes.create.rewardPlanPlaceholder")}
                      options={plans.map((plan) => ({ value: String(plan.id), label: plan.name }))}
                    />
                  )}
                </div>
                <div className="flex flex-col gap-1">
                  <label htmlFor="promo-reward-duration" className={labelClassName}>
                    {t("promocodes.create.rewardDurationDaysLabel")}
                  </label>
                  <div className="flex items-center rounded-xl border border-border bg-input/60 focus-within:border-primary">
                    <input
                      id="promo-reward-duration"
                      type="number"
                      min={1}
                      step="1"
                      value={rewardDurationDays}
                      onChange={(event) => setRewardDurationDays(event.target.value)}
                      className="min-w-0 flex-1 bg-transparent px-3 py-2 text-sm text-foreground outline-none"
                    />
                    {daysSuffix}
                  </div>
                </div>
              </div>
            )}
          </section>

          <PromocodeLimitsFields idPrefix="promo" value={limits} onChange={setLimits} />
        </div>

        <div className="flex shrink-0 items-center gap-2 border-t border-white/[0.07] px-5 py-3.5">
          <p className="min-w-0 flex-1 truncate text-[12.5px] text-muted-foreground">
            <span className="font-mono font-bold text-foreground">{code.trim() || "—"}</span>
            {" · "}
            <span className="font-semibold text-primary">{describeReward(draftReward, addons, plans, t)}</span>
            {" · "}
            {t(`promocodes.availability.${limits.availability}`)}
          </p>
          <button
            type="button"
            onClick={close}
            className="shrink-0 rounded-full border border-border px-4 py-2 text-sm font-medium text-foreground/80 transition-colors hover:bg-white/5"
          >
            {t("promocodes.create.cancel")}
          </button>
          <motion.button
            type="submit"
            disabled={isSubmitting}
            {...bounceTap(bounceStrength)}
            className="shrink-0 rounded-full bg-accent px-4 py-2 text-sm font-medium text-primary transition-colors hover:bg-primary/20 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isSubmitting ? t("promocodes.create.saving") : t("promocodes.create.save")}
          </motion.button>
        </div>
      </form>
    </>
  );
}
