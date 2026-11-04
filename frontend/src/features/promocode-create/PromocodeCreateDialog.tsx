import { Dices, Package, Ticket } from "lucide-react";
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
  limitsToPayload,
  PLAN_LIMITED_REWARDS,
  type PromocodeLimitsDraft,
  REWARD_TYPE_ICON,
  REWARD_TYPES,
} from "@entities/promocodes/display";
import {
  PromocodeLimitsFields,
} from "@entities/promocodes/PromocodeLimitsFields";
import { getErrorMessage } from "@shared/api/http";
import { blockNonIntegerKeys, parseRequiredInt } from "@shared/lib/number-input";
import { toast } from "@shared/lib/toast";
import { Modal } from "@shared/ui/Modal";
import { useModalClose } from "@shared/ui/modal-hooks";
import { SelectDropdown } from "@shared/ui/SelectDropdown";
import { Button } from "@shared/ui/Button";
import { GLASS_DIALOG_CARD_CLASS } from "@shared/ui/classes";
import { DialogHeader } from "@shared/ui/glass/DialogHeader";
import { Field } from "@shared/ui/glass/Field";
import { Input } from "@shared/ui/glass/Input";
import { ChoiceChip } from "@shared/ui/ChoiceChip";
import { Pressable } from "@shared/ui/Pressable";

const DAY_PRESETS = [1, 3, 7, 14, 30, 60];
const DISABLED_REWARD_TYPES: PromocodeRewardType[] = ["TRAFFIC", "DEVICES"];

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
    allowedPlanIds: [],
    expiresAt: "",
    maxActivations: "",
    isReusable: false,
  });

  const trimmedCode = code.trim();
  const isCodeInvalid = trimmedCode !== "" && !PROMOCODE_CODE_PATTERN.test(trimmedCode);

  const matchingAddons = addons.filter((addon) => addon.type === rewardType);
  const isDiscount = rewardType === "PERSONAL_DISCOUNT" || rewardType === "PURCHASE_DISCOUNT";

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

    const limitsPayload = limitsToPayload(limits, rewardType);
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
        <div className="scroll-fade-y flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto p-3 [--dialog-pad:0.75rem]">
          <div className={GLASS_DIALOG_CARD_CLASS}>
            <Field
              label={t("promocodes.sections.code")}
              htmlFor="promo-code"
              required
              error={isCodeInvalid ? t("promocodes.create.codeInvalid") : undefined}
            >
              <div className="flex gap-2">
                <Input
                  id="promo-code"
                  value={code}
                  onChange={(event) => setCode(event.target.value.toUpperCase())}
                  placeholder={t("promocodes.create.codePlaceholder")}
                  autoComplete="off"
                  maxLength={PROMOCODE_CODE_MAX_LENGTH}
                  aria-invalid={isCodeInvalid}
                  mono
                  className="min-w-0 flex-1"
                />
                {canGenerateCode && (
                  <Button
                    variant="glass"
                    onClick={() => void handleGenerate()}
                    icon={Dices}
                    isLoading={isGenerating}
                  >
                    {t("promocodes.create.generate")}
                  </Button>
                )}
              </div>
            </Field>
          </div>

          <div className={GLASS_DIALOG_CARD_CLASS}>
            <Field label={t("promocodes.sections.reward")}>
              <div className="grid auto-rows-fr grid-cols-3 gap-2">
                {REWARD_TYPES.map((type) => {
                  const Icon = REWARD_TYPE_ICON[type];
                  const isSelected = rewardType === type;
                  return (
                    <Pressable
                      key={type}
                      type="button"
                      disabled={DISABLED_REWARD_TYPES.includes(type)}
                      onClick={() => setRewardType(type)}
                      className={`flex flex-col items-start gap-2 rounded-[10px] border p-3 text-left transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${
                        isSelected
                          ? "border-primary/35 bg-primary/15 text-primary"
                          : "border-glass-border bg-white/[0.03] text-foreground enabled:hover:bg-white/[0.06]"
                      }`}
                    >
                      <Icon className={`size-4 ${isSelected ? "" : "text-muted-foreground"}`} />
                      <span className="text-[13px] font-medium">{t(`promocodes.rewardTypeShort.${type}`)}</span>
                    </Pressable>
                  );
                })}
              </div>
            </Field>

            {rewardType === "DURATION" && (
              <Field label={t("promocodes.create.rewardDaysLabel")} htmlFor="promo-reward-days">
                {/* the reward cards' grid: the field as wide as one card */}
                <div className="grid grid-cols-3 items-center gap-2">
                  <Input
                    id="promo-reward-days"
                    type="number"
                    onKeyDown={blockNonIntegerKeys}
                    min={1}
                    step="1"
                    value={rewardDays}
                    onChange={(event) => setRewardDays(event.target.value)}
                    suffix={daysSuffix}
                  />
                  <div className="col-span-2 grid grid-cols-6 gap-1.5">
                    {DAY_PRESETS.map((days) => (
                      <ChoiceChip
                        glass
                        // 36px, the field's height beside it
                        className="h-9"
                        key={days}
                        onClick={() => setRewardDays(String(days))}
                        active={rewardDays === String(days)}
                      >
                        {days}
                      </ChoiceChip>
                    ))}
                  </div>
                </div>
              </Field>
            )}

            {isDiscount && (
              <Field label={t("promocodes.create.rewardPercentLabel")} htmlFor="promo-reward-percent">
                <Input
                  id="promo-reward-percent"
                  type="number"
                  onKeyDown={blockNonIntegerKeys}
                  min={0}
                  max={100}
                  step="1"
                  value={rewardPercent}
                  onChange={(event) => setRewardPercent(event.target.value)}
                  suffix="%"
                />
              </Field>
            )}

            {(rewardType === "TRAFFIC" || rewardType === "DEVICES") && (
              <Field label={t("promocodes.create.rewardAddonLabel")} htmlFor="promo-reward-addon">
                {matchingAddons.length === 0 ? (
                  <p className="text-[12px] text-muted-foreground">{t("promocodes.create.rewardAddonEmpty")}</p>
                ) : (
                  <SelectDropdown
                    variant="well"
                    size="compact"
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
                    <p className="text-[12px] text-muted-foreground">{t("promocodes.create.rewardPlanEmpty")}</p>
                  ) : (
                    <SelectDropdown
                      variant="well"
                      size="compact"
                      id="promo-reward-plan"
                      value={rewardPlanId}
                      onChange={setRewardPlanId}
                      icon={Package}
                      placeholder={t("promocodes.create.rewardPlanPlaceholder")}
                      options={plans.map((plan) => ({ value: String(plan.id), label: plan.name }))}
                    />
                  )}
                </Field>
                <Field label={t("promocodes.create.rewardDurationDaysLabel")} htmlFor="promo-reward-duration">
                  <Input
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
          </div>

          <PromocodeLimitsFields
            idPrefix="promo"
            value={limits}
            onChange={setLimits}
            plans={PLAN_LIMITED_REWARDS.includes(rewardType) ? plans : undefined}
          />
        </div>

        <div className="flex shrink-0 items-center justify-end gap-2 border-t border-white/[0.08] p-4">
          <Button variant="glass" type="button" onClick={close}>
            {t("common.cancel")}
          </Button>
          <Button variant="glassAccent" type="submit" disabled={isCodeInvalid} isLoading={isSubmitting}>
            {t("common.create")}
          </Button>
        </div>
      </form>
    </>
  );
}
