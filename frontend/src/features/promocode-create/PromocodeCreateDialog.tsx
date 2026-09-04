import { Dices, Filter, Plus, X } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { type AddOnListItem, listAddons } from "@entities/addons/api";
import { type Plan, listPlans } from "@entities/plans/api";
import {
  type CreatePromocodeRequest,
  createPromocode,
  generatePromocodeCode,
  type Promocode,
  type PromocodeAvailability,
  type PromocodeRewardType,
} from "@entities/promocodes/api";
import { getErrorMessage } from "@shared/api/http";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { parseOptionalInt, parseRequiredInt } from "@shared/lib/number-input";
import { toast } from "@shared/lib/toast";
import { DatePickerField } from "@shared/ui/DatePickerField";
import { Modal, useModalClose } from "@shared/ui/Modal";
import { SelectDropdown } from "@shared/ui/SelectDropdown";
import { Switch } from "@shared/ui/Switch";

const REWARD_TYPES: PromocodeRewardType[] = [
  "DURATION",
  "TRAFFIC",
  "DEVICES",
  "SUBSCRIPTION",
  "PERSONAL_DISCOUNT",
  "PURCHASE_DISCOUNT",
];
const AVAILABILITIES: PromocodeAvailability[] = ["ALL", "NEW", "EXISTING", "INVITED", "ALLOWED"];

interface PromocodeCreateDialogProps {
  canGenerateCode: boolean;
  onClose: () => void;
  onSaved: (promocode: Promocode) => void;
}

const fieldClassName =
  "rounded-xl border border-border bg-input/60 px-3 py-2 text-sm text-foreground outline-none focus:border-primary";

function parseLines(value: string): string[] {
  return value
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length > 0);
}

export function PromocodeCreateDialog({ canGenerateCode, onClose, onSaved }: PromocodeCreateDialogProps) {
  return (
    <Modal onClose={onClose} size="lg" scrollable>
      <PromocodeCreateDialogBody canGenerateCode={canGenerateCode} onSaved={onSaved} />
    </Modal>
  );
}

function PromocodeCreateDialogBody({
  canGenerateCode,
  onSaved,
}: Pick<PromocodeCreateDialogProps, "canGenerateCode" | "onSaved">) {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const close = useModalClose();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [addons, setAddons] = useState<AddOnListItem[]>([]);
  const [plans, setPlans] = useState<Plan[]>([]);

  const [code, setCode] = useState("");
  const [rewardType, setRewardType] = useState<PromocodeRewardType>("DURATION");
  const [rewardDays, setRewardDays] = useState("30");
  const [rewardPercent, setRewardPercent] = useState("10");
  const [rewardAddonId, setRewardAddonId] = useState("");
  const [rewardPlanId, setRewardPlanId] = useState("");
  const [rewardDurationDays, setRewardDurationDays] = useState("30");
  const [availability, setAvailability] = useState<PromocodeAvailability>("ALL");
  const [allowedUserIds, setAllowedUserIds] = useState("");
  const [expiresAt, setExpiresAt] = useState("");
  const [maxActivations, setMaxActivations] = useState("");
  const [isReusable, setIsReusable] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    listAddons(controller.signal)
      .then((items) => {
        if (!controller.signal.aborted) setAddons(items);
      })
      .catch(() => {
        if (!controller.signal.aborted) setAddons([]);
      });
    listPlans(controller.signal)
      .then((items) => {
        if (!controller.signal.aborted) setPlans(items);
      })
      .catch(() => {
        if (!controller.signal.aborted) setPlans([]);
      });
    return () => controller.abort();
  }, []);

  const matchingAddons = addons.filter((addon) => addon.type === rewardType);

  const handleGenerate = async () => {
    try {
      setCode(await generatePromocodeCode());
    } catch (err) {
      toast.error(getErrorMessage(err, t("promocodes.create.error")));
    }
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();

    const parsedMaxActivations = parseOptionalInt(maxActivations, 1);
    if (parsedMaxActivations === undefined) {
      toast.error(t("errors.invalidNumber"));
      return;
    }

    const payload: CreatePromocodeRequest = {
      code: code.trim().toUpperCase(),
      reward_type: rewardType,
      availability,
      allowed_user_ids: parseLines(allowedUserIds)
        .map((id) => Number(id))
        .filter((id) => Number.isFinite(id)),
      expires_at: expiresAt ? `${expiresAt}T23:59:59.000Z` : null,
      max_activations: parsedMaxActivations,
      is_reusable: isReusable,
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

  return (
    <>
      <div className="flex shrink-0 items-center justify-between border-b border-border px-5 py-4">
        <h2 className="flex items-center gap-2.5 text-base font-bold text-foreground">
          <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] text-foreground backdrop-blur-md">
            <Plus className="size-4" />
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

      <form onSubmit={(event) => void handleSubmit(event)} className="flex min-h-0 flex-1 flex-col overflow-y-auto">
        <div className="flex flex-col gap-4 px-5 pb-4 pt-4">
          <div className="flex flex-col gap-1">
            <label htmlFor="promo-code" className="text-sm font-medium text-foreground/80">
              {t("promocodes.create.codeLabel")}
            </label>
            <div className="flex gap-2">
              <input
                id="promo-code"
                value={code}
                onChange={(event) => setCode(event.target.value.toUpperCase())}
                placeholder={t("promocodes.create.codePlaceholder")}
                className={`${fieldClassName} flex-1 font-mono`}
              />
              {canGenerateCode && (
                <motion.button
                  type="button"
                  onClick={() => void handleGenerate()}
                  {...bounceTap(bounceStrength)}
                  className="flex shrink-0 items-center gap-1.5 rounded-full border border-border px-3 text-[12.5px] font-medium text-foreground/90 transition-colors hover:bg-white/5"
                >
                  <Dices className="size-3.5" />
                  {t("promocodes.create.generate")}
                </motion.button>
              )}
            </div>
          </div>

          <div className="flex flex-col gap-1">
            <span className="text-sm font-medium text-foreground/80">{t("promocodes.create.rewardTypeLabel")}</span>
            <SelectDropdown
              id="promo-reward-type"
              value={rewardType}
              onChange={(value) => setRewardType(value as PromocodeRewardType)}
              icon={Filter}
              placeholder={t(`promocodes.rewardType.${rewardType}`)}
              options={REWARD_TYPES.map((value) => ({ value, label: t(`promocodes.rewardType.${value}`) }))}
            />
          </div>

          {rewardType === "DURATION" && (
            <div className="flex flex-col gap-1">
              <label htmlFor="promo-reward-days" className="text-sm font-medium text-foreground/80">
                {t("promocodes.create.rewardDaysLabel")}
              </label>
              <input
                id="promo-reward-days"
                type="number"
                min={1}
                step="1"
                value={rewardDays}
                onChange={(event) => setRewardDays(event.target.value)}
                className={fieldClassName}
              />
            </div>
          )}

          {(rewardType === "PERSONAL_DISCOUNT" || rewardType === "PURCHASE_DISCOUNT") && (
            <div className="flex flex-col gap-1">
              <label htmlFor="promo-reward-percent" className="text-sm font-medium text-foreground/80">
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
                className={fieldClassName}
              />
            </div>
          )}

          {(rewardType === "TRAFFIC" || rewardType === "DEVICES") && (
            <div className="flex flex-col gap-1">
              <span className="text-sm font-medium text-foreground/80">{t("promocodes.create.rewardAddonLabel")}</span>
              {matchingAddons.length === 0 ? (
                <p className="text-[12.5px] text-muted-foreground">{t("promocodes.create.rewardAddonEmpty")}</p>
              ) : (
                <SelectDropdown
                  id="promo-reward-addon"
                  value={rewardAddonId}
                  onChange={setRewardAddonId}
                  icon={Filter}
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
            <div className="flex gap-3">
              <div className="flex flex-1 flex-col gap-1">
                <span className="text-sm font-medium text-foreground/80">{t("promocodes.create.rewardPlanLabel")}</span>
                {plans.length === 0 ? (
                  <p className="text-[12.5px] text-muted-foreground">{t("promocodes.create.rewardPlanEmpty")}</p>
                ) : (
                  <SelectDropdown
                    id="promo-reward-plan"
                    value={rewardPlanId}
                    onChange={setRewardPlanId}
                    icon={Filter}
                    placeholder={t("promocodes.create.rewardPlanPlaceholder")}
                    options={plans.map((plan) => ({ value: String(plan.id), label: plan.name }))}
                  />
                )}
              </div>
              <div className="flex flex-1 flex-col gap-1">
                <label htmlFor="promo-reward-duration" className="text-sm font-medium text-foreground/80">
                  {t("promocodes.create.rewardDurationDaysLabel")}
                </label>
                <input
                  id="promo-reward-duration"
                  type="number"
                  min={1}
                  step="1"
                  value={rewardDurationDays}
                  onChange={(event) => setRewardDurationDays(event.target.value)}
                  className={fieldClassName}
                />
              </div>
            </div>
          )}

          <div className="flex flex-col gap-1">
            <span className="text-sm font-medium text-foreground/80">{t("promocodes.create.availabilityLabel")}</span>
            <SelectDropdown
              id="promo-availability"
              value={availability}
              onChange={(value) => setAvailability(value as PromocodeAvailability)}
              icon={Filter}
              placeholder={t(`promocodes.availability.${availability}`)}
              options={AVAILABILITIES.map((value) => ({ value, label: t(`promocodes.availability.${value}`) }))}
            />
          </div>

          <div className="flex flex-col gap-1">
            <label htmlFor="promo-allowed-users" className="text-sm font-medium text-foreground/80">
              {t("promocodes.create.allowedUserIdsLabel")}
            </label>
            <textarea
              id="promo-allowed-users"
              value={allowedUserIds}
              onChange={(event) => setAllowedUserIds(event.target.value)}
              rows={3}
              className={`${fieldClassName} resize-none font-mono`}
            />
            <span className="text-[11.5px] text-muted-foreground">{t("promocodes.create.allowedUserIdsHint")}</span>
          </div>

          <div className="flex gap-3">
            <div className="flex flex-1 flex-col gap-1">
              <span className="text-sm font-medium text-foreground/80">{t("promocodes.create.expiresLabel")}</span>
              <DatePickerField
                id="promo-expires-at"
                value={expiresAt}
                onChange={setExpiresAt}
                placeholder={t("promocodes.create.expiresPlaceholder")}
                clearAriaLabel={t("promocodes.create.clearDate")}
              />
            </div>
            <div className="flex flex-1 flex-col gap-1">
              <label htmlFor="promo-max-activations" className="text-sm font-medium text-foreground/80">
                {t("promocodes.create.maxActivationsLabel")}
              </label>
              <input
                id="promo-max-activations"
                type="number"
                min={1}
                step="1"
                value={maxActivations}
                onChange={(event) => setMaxActivations(event.target.value)}
                placeholder={t("promocodes.create.maxActivationsHint")}
                className={fieldClassName}
              />
            </div>
          </div>

          <label className="flex items-center gap-2.5 text-sm font-medium text-foreground/80">
            <Switch checked={isReusable} onChange={setIsReusable} ariaLabel={t("promocodes.create.reusableLabel")} />
            {t("promocodes.create.reusableLabel")}
          </label>
        </div>

        <div className="flex shrink-0 gap-2 border-t border-border px-5 py-4">
          <button
            type="button"
            onClick={close}
            className="flex-1 rounded-full border border-border px-4 py-2 text-sm font-medium text-foreground/80 transition-colors hover:bg-white/5"
          >
            {t("promocodes.create.cancel")}
          </button>
          <motion.button
            type="submit"
            disabled={isSubmitting}
            {...bounceTap(bounceStrength)}
            className="flex-1 rounded-full bg-accent px-4 py-2 text-sm font-medium text-primary transition-colors hover:bg-primary/20 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isSubmitting ? t("promocodes.create.saving") : t("promocodes.create.save")}
          </motion.button>
        </div>
      </form>
    </>
  );
}
