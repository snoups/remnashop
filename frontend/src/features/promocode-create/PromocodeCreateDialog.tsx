import { Dices, Loader2, Package, Tag, Ticket } from "lucide-react";
import { motion } from "motion/react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import type { AddOnListItem } from "@entities/addons/api";
import type { Plan } from "@entities/plans/api";
import {
  type CreatePromocodeRequest,
  createPromocode,
  generatePromocodeCode,
  PROMOCODE_CODE_MAX_LENGTH,
  PROMOCODE_CODE_PATTERN,
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
} from "@entities/promocodes/PromocodeLimitsFields";
import { getErrorMessage } from "@shared/api/http";
import { bounceTap } from "@shared/lib/bounceState";
import { blockNonIntegerKeys, parseRequiredInt } from "@shared/lib/number-input";
import { toast } from "@shared/lib/toast";
import { Modal } from "@shared/ui/Modal";
import { useModalClose } from "@shared/ui/modal-hooks";
import { SelectDropdown } from "@shared/ui/SelectDropdown";
import { Button } from "@shared/ui/Button";
import { DialogHeader } from "@shared/ui/DialogHeader";
import { SuffixInput, TextInput } from "@shared/ui/TextInput";
import { Card } from "@shared/ui/Card";
import { Field } from "@shared/ui/Field";
import { ChoiceChip } from "@shared/ui/ChoiceChip";

const DAY_PRESETS = [7, 30, 90];

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

  const trimmedCode = code.trim();
  const isCodeInvalid = trimmedCode !== "" && !PROMOCODE_CODE_PATTERN.test(trimmedCode);
  const canSubmit = trimmedCode !== "" && !isCodeInvalid;

  const matchingAddons = addons.filter((addon) => addon.type === rewardType);
  const isDiscount = rewardType === "PERSONAL_DISCOUNT" || rewardType === "PURCHASE_DISCOUNT";

  const draftReward: PromocodeReward = {
    reward_type: rewardType,
    reward: rewardType === "DURATION" ? Number(rewardDays) || 0 : isDiscount ? Number(rewardPercent) || 0 : null,
    reward_addon_id: rewardAddonId ? Number(rewardAddonId) : null,
    reward_plan_id: rewardPlanId ? Number(rewardPlanId) : null,
    reward_duration_days: Number(rewardDurationDays) || 0,
  };

  const [isGenerating, setIsGenerating] = useState(false);

  const handleGenerate = async () => {
    setIsGenerating(true);
    try {
      setCode(await generatePromocodeCode());
    } catch (err) {
      toast.error(getErrorMessage(err, t("promocodes.create.error")));
    } finally {
      setIsGenerating(false);
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
      code: trimmedCode,
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

  const daysSuffix = t("promocodes.create.daysSuffix");

  return (
    <>
      <DialogHeader icon={Ticket} title={t("promocodes.create.title")} />

      <form onSubmit={(event) => void handleSubmit(event)} className="flex min-h-0 flex-1 flex-col">
        <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto p-4">
          <Card variant="form">
            <Field label={t("promocodes.sections.code")} htmlFor="promo-code" required>
              <div className="flex gap-2">
                <TextInput
                  id="promo-code"
                  value={code}
                  onChange={(event) => setCode(event.target.value.toUpperCase())}
                  placeholder={t("promocodes.create.codePlaceholder")}
                  autoComplete="off"
                  maxLength={PROMOCODE_CODE_MAX_LENGTH}
                  aria-invalid={isCodeInvalid}
                  className="min-w-0 flex-1 font-mono tracking-wider"
                />
                {canGenerateCode && (
                  <Button
                    variant="secondary"
                    size="field"
                    onClick={() => void handleGenerate()}
                    disabled={isGenerating}
                  >
                    {isGenerating ? <Loader2 className="size-3.5 animate-spin" /> : <Dices className="size-3.5" />}
                    {t("promocodes.create.generate")}
                  </Button>
                )}
              </div>
              {isCodeInvalid && (
                <p id="promo-code-hint" className="text-[12px] text-error">
                  {t("promocodes.create.codeInvalid")}
                </p>
              )}
            </Field>
          </Card>

          <Card variant="form">
            <Field label={t("promocodes.sections.reward")}>
              <div className="grid grid-cols-3 gap-2">
                {REWARD_TYPES.map((type) => {
                  const Icon = REWARD_TYPE_ICON[type];
                  const isSelected = rewardType === type;
                  return (
                    <motion.button
                      key={type}
                      type="button"
                      onClick={() => setRewardType(type)}
                      {...bounceTap(0.03)}
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
            </Field>

            {rewardType === "DURATION" && (
              <Field label={t("promocodes.create.rewardDaysLabel")} htmlFor="promo-reward-days">
                <div className="flex items-center gap-2">
                  <SuffixInput
                    id="promo-reward-days"
                    type="number"
                    onKeyDown={blockNonIntegerKeys}
                    min={1}
                    step="1"
                    value={rewardDays}
                    onChange={(event) => setRewardDays(event.target.value)}
                    suffix={daysSuffix}
                    className="flex-1"
                  />
                  {DAY_PRESETS.map((days) => (
                    <ChoiceChip
                      key={days}
                      onClick={() => setRewardDays(String(days))}
                      active={rewardDays === String(days)}
                    >
                      {days}
                    </ChoiceChip>
                  ))}
                </div>
              </Field>
            )}

            {isDiscount && (
              <Field label={t("promocodes.create.rewardPercentLabel")} htmlFor="promo-reward-percent">
                <TextInput
                  id="promo-reward-percent"
                  type="number"
                  onKeyDown={blockNonIntegerKeys}
                  min={0}
                  max={100}
                  step="1"
                  value={rewardPercent}
                  onChange={(event) => setRewardPercent(event.target.value)}
                />
              </Field>
            )}

            {(rewardType === "TRAFFIC" || rewardType === "DEVICES") && (
              <Field label={t("promocodes.create.rewardAddonLabel")} htmlFor="promo-reward-addon">
                {matchingAddons.length === 0 ? (
                  <p className="text-[12.5px] text-muted-foreground">{t("promocodes.create.rewardAddonEmpty")}</p>
                ) : (
                  <SelectDropdown
                    variant="form"
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
              </Field>
            )}

            {rewardType === "SUBSCRIPTION" && (
              <div className="grid grid-cols-[minmax(0,3fr)_minmax(0,2fr)] gap-3">
                <Field label={t("promocodes.create.rewardPlanLabel")} htmlFor="promo-reward-plan">
                  {plans.length === 0 ? (
                    <p className="text-[12.5px] text-muted-foreground">{t("promocodes.create.rewardPlanEmpty")}</p>
                  ) : (
                    <SelectDropdown
                      variant="form"
                      id="promo-reward-plan"
                      value={rewardPlanId}
                      onChange={setRewardPlanId}
                      icon={Tag}
                      placeholder={t("promocodes.create.rewardPlanPlaceholder")}
                      options={plans.map((plan) => ({ value: String(plan.id), label: plan.name }))}
                    />
                  )}
                </Field>
                <Field label={t("promocodes.create.rewardDurationDaysLabel")} htmlFor="promo-reward-duration">
                  <SuffixInput
                    id="promo-reward-duration"
                    type="number"
                    onKeyDown={blockNonIntegerKeys}
                    min={1}
                    step="1"
                    value={rewardDurationDays}
                    onChange={(event) => setRewardDurationDays(event.target.value)}
                    suffix={daysSuffix}
                  />
                </Field>
              </div>
            )}
          </Card>

          <PromocodeLimitsFields idPrefix="promo" value={limits} onChange={setLimits} />
        </div>

        <div className="flex shrink-0 items-center gap-2 border-t border-white/[0.07] px-5 py-4">
          <p className="min-w-0 flex-1 truncate text-[12.5px] text-muted-foreground">
            <span className="font-mono font-bold text-foreground">{trimmedCode || "—"}</span>
            {" · "}
            <span className="font-semibold text-primary">{describeReward(draftReward, addons, plans, t)}</span>
            {" · "}
            {t(`promocodes.availability.${limits.availability}`)}
          </p>
          <Button
            variant="outline"
            type="button"
            onClick={close}
          >
            {t("promocodes.create.cancel")}
          </Button>
          <Button variant="accent" type="submit" disabled={isSubmitting || !canSubmit}>
            {isSubmitting ? t("promocodes.create.saving") : t("promocodes.create.save")}
          </Button>
        </div>
      </form>
    </>
  );
}
