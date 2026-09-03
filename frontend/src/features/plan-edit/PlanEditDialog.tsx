import { Filter, Pencil, Plus, Trash2, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import {
  type CreatePlanRequest,
  createPlan,
  type Plan,
  type PlanType,
  setPlanDurations,
  type TrafficLimitStrategy,
  updatePlan,
} from "@entities/plans/api";
import { getErrorMessage } from "@shared/api/http";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { toast } from "@shared/lib/toast";
import { DialogPortal } from "@shared/ui/DialogPortal";
import { SelectDropdown } from "@shared/ui/SelectDropdown";
import { Switch } from "@shared/ui/Switch";

const PLAN_TYPES: PlanType[] = ["TRAFFIC", "DEVICES", "BOTH", "UNLIMITED"];
const STRATEGIES: TrafficLimitStrategy[] = ["NO_RESET", "DAY", "WEEK", "MONTH", "MONTH_ROLLING"];

interface DurationRow {
  days: string;
  base_price: string;
}

interface PlanEditDialogProps {
  plan: Plan | null;
  onClose: () => void;
  onSaved: (plan: Plan) => void;
}

const fieldClassName =
  "rounded-xl border border-border bg-input/60 px-3 py-2 text-sm text-foreground outline-none focus:border-primary";

export function PlanEditDialog({ plan, onClose, onSaved }: PlanEditDialogProps) {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const isCreate = plan === null;
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [publicCode, setPublicCode] = useState(plan?.public_code ?? "");
  const [name, setName] = useState(plan?.name ?? "");
  const [description, setDescription] = useState(plan?.description ?? "");
  const [tag, setTag] = useState(plan?.tag ?? "");
  const [type, setType] = useState<PlanType>(plan?.type ?? "BOTH");
  const [strategy, setStrategy] = useState<TrafficLimitStrategy>(plan?.traffic_limit_strategy ?? "NO_RESET");
  const [trafficLimit, setTrafficLimit] = useState(String(plan?.traffic_limit ?? 0));
  const [deviceLimit, setDeviceLimit] = useState(String(plan?.device_limit ?? 0));
  const [isTrial, setIsTrial] = useState(plan?.is_trial ?? false);
  const [isActive, setIsActive] = useState(plan?.is_active ?? true);
  const [durations, setDurations] = useState<DurationRow[]>(
    (plan?.durations ?? []).map((d) => ({ days: String(d.days), base_price: d.base_price })),
  );

  const addDuration = () => setDurations((rows) => [...rows, { days: "30", base_price: "0" }]);
  const removeDuration = (index: number) => setDurations((rows) => rows.filter((_, i) => i !== index));
  const updateDuration = (index: number, patch: Partial<DurationRow>) =>
    setDurations((rows) => rows.map((row, i) => (i === index ? { ...row, ...patch } : row)));

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setIsSubmitting(true);
    try {
      if (isCreate) {
        const payload: CreatePlanRequest = {
          public_code: publicCode.trim(),
          name: name.trim(),
          description: description.trim() || null,
          tag: tag.trim() || null,
          type,
          traffic_limit_strategy: strategy,
          traffic_limit: Math.max(0, Math.round(Number(trafficLimit))),
          device_limit: Math.max(0, Math.round(Number(deviceLimit))),
          is_trial: isTrial,
        };
        const created = await createPlan(payload);
        toast.success(t("plans.edit.saved"));
        onSaved(created);
      } else {
        let updated = await updatePlan(plan.id, {
          name: name.trim(),
          description: description.trim() || null,
          tag: tag.trim() || null,
          type,
          traffic_limit_strategy: strategy,
          traffic_limit: Math.max(0, Math.round(Number(trafficLimit))),
          device_limit: Math.max(0, Math.round(Number(deviceLimit))),
          is_active: isActive,
          is_trial: isTrial,
        });
        updated = await setPlanDurations(
          plan.id,
          durations.map((row, index) => ({
            days: Math.max(1, Math.round(Number(row.days))),
            order_index: index,
            base_price: row.base_price,
          })),
        );
        toast.success(t("plans.edit.saved"));
        onSaved(updated);
      }
      onClose();
    } catch (err) {
      toast.error(getErrorMessage(err, t("plans.edit.error")));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <DialogPortal>
      <AnimatePresence>
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15, ease: "easeOut" }}
          className="fixed inset-0 z-40 flex items-center justify-center bg-black/55 backdrop-blur-3xl p-4"
        >
          <button
            type="button"
            aria-hidden
            tabIndex={-1}
            className="absolute inset-0 cursor-default"
            onClick={onClose}
          />

          <motion.div
            initial={{ opacity: 0, scale: 0.94, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.94, y: 8 }}
            transition={{ duration: 0.18, ease: "easeOut" }}
            className="relative z-50 flex max-h-[85vh] w-full max-w-lg flex-col rounded-dialog border border-white/[0.14] bg-popover/60 shadow-[0_24px_48px_-20px_rgba(4,8,20,0.6),inset_0_1px_0_rgba(232,236,251,0.16)] backdrop-blur-2xl backdrop-saturate-150"
          >
            <div className="flex shrink-0 items-center justify-between border-b border-border px-5 py-4">
              <h2 className="flex items-center gap-2.5 text-base font-bold text-foreground">
                <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] text-foreground backdrop-blur-md">
                  <Pencil className="size-4" />
                </div>
                {isCreate ? t("plans.edit.createTitle") : t("plans.edit.editTitle")}
              </h2>
              <button
                type="button"
                onClick={onClose}
                aria-label={t("plans.edit.close")}
                className="flex size-8 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-white/[0.06] hover:text-foreground"
              >
                <X className="size-4" />
              </button>
            </div>

            <form
              onSubmit={(event) => void handleSubmit(event)}
              className="flex min-h-0 flex-1 flex-col overflow-y-auto"
            >
              <div className="flex flex-col gap-4 px-5 pb-4 pt-4">
                <div className="flex gap-3">
                  <div className="flex flex-1 flex-col gap-1">
                    <label htmlFor="plan-public-code" className="text-sm font-medium text-foreground/80">
                      {t("plans.edit.publicCodeLabel")}
                    </label>
                    <input
                      id="plan-public-code"
                      value={publicCode}
                      onChange={(event) => setPublicCode(event.target.value)}
                      placeholder={t("plans.edit.publicCodePlaceholder")}
                      disabled={!isCreate}
                      className={`${fieldClassName} disabled:cursor-not-allowed disabled:opacity-50`}
                    />
                  </div>
                  <div className="flex flex-1 flex-col gap-1">
                    <label htmlFor="plan-name" className="text-sm font-medium text-foreground/80">
                      {t("plans.edit.nameLabel")}
                    </label>
                    <input
                      id="plan-name"
                      value={name}
                      onChange={(event) => setName(event.target.value)}
                      className={fieldClassName}
                    />
                  </div>
                </div>

                <div className="flex flex-col gap-1">
                  <label htmlFor="plan-description" className="text-sm font-medium text-foreground/80">
                    {t("plans.edit.descriptionLabel")}
                  </label>
                  <textarea
                    id="plan-description"
                    value={description}
                    onChange={(event) => setDescription(event.target.value)}
                    rows={2}
                    className={`${fieldClassName} resize-none`}
                  />
                </div>

                <div className="flex gap-3">
                  <div className="flex flex-1 flex-col gap-1">
                    <label htmlFor="plan-tag" className="text-sm font-medium text-foreground/80">
                      {t("plans.edit.tagLabel")}
                    </label>
                    <input
                      id="plan-tag"
                      value={tag}
                      onChange={(event) => setTag(event.target.value)}
                      className={fieldClassName}
                    />
                  </div>
                  <div className="flex flex-1 flex-col gap-1">
                    <span className="text-sm font-medium text-foreground/80">{t("plans.edit.typeLabel")}</span>
                    <SelectDropdown
                      id="plan-type"
                      value={type}
                      onChange={(value) => setType(value as PlanType)}
                      icon={Filter}
                      placeholder={t(`plans.edit.type.${type}`)}
                      options={PLAN_TYPES.map((value) => ({ value, label: t(`plans.edit.type.${value}`) }))}
                    />
                  </div>
                </div>

                <div className="flex gap-3">
                  <div className="flex flex-1 flex-col gap-1">
                    <label htmlFor="plan-traffic" className="text-sm font-medium text-foreground/80">
                      {t("plans.edit.trafficLabel")}
                    </label>
                    <input
                      id="plan-traffic"
                      type="number"
                      min={0}
                      step="1"
                      value={trafficLimit}
                      onChange={(event) => setTrafficLimit(event.target.value)}
                      className={fieldClassName}
                    />
                    <span className="text-[11.5px] text-muted-foreground">{t("plans.edit.trafficHint")}</span>
                  </div>
                  <div className="flex flex-1 flex-col gap-1">
                    <label htmlFor="plan-devices" className="text-sm font-medium text-foreground/80">
                      {t("plans.edit.deviceLabel")}
                    </label>
                    <input
                      id="plan-devices"
                      type="number"
                      min={0}
                      step="1"
                      value={deviceLimit}
                      onChange={(event) => setDeviceLimit(event.target.value)}
                      className={fieldClassName}
                    />
                    <span className="text-[11.5px] text-muted-foreground">{t("plans.edit.deviceHint")}</span>
                  </div>
                </div>

                <div className="flex flex-col gap-1">
                  <span className="text-sm font-medium text-foreground/80">{t("plans.edit.strategyLabel")}</span>
                  <SelectDropdown
                    id="plan-strategy"
                    value={strategy}
                    onChange={(value) => setStrategy(value as TrafficLimitStrategy)}
                    icon={Filter}
                    placeholder={t(`plans.edit.strategy.${strategy}`)}
                    options={STRATEGIES.map((value) => ({ value, label: t(`plans.edit.strategy.${value}`) }))}
                  />
                </div>

                <div className="flex items-center gap-6">
                  <label className="flex items-center gap-2.5 text-sm font-medium text-foreground/80">
                    <Switch checked={isTrial} onChange={setIsTrial} ariaLabel={t("plans.edit.isTrialLabel")} />
                    {t("plans.edit.isTrialLabel")}
                  </label>
                  {!isCreate && (
                    <label className="flex items-center gap-2.5 text-sm font-medium text-foreground/80">
                      <Switch checked={isActive} onChange={setIsActive} ariaLabel={t("plans.edit.isActiveLabel")} />
                      {t("plans.edit.isActiveLabel")}
                    </label>
                  )}
                </div>

                {!isCreate && (
                  <div className="flex flex-col gap-2 border-t border-border pt-4">
                    <span className="text-sm font-medium text-foreground/80">{t("plans.edit.durationsTitle")}</span>
                    <p className="text-[11.5px] text-muted-foreground">{t("plans.edit.durationsHint")}</p>
                    {durations.map((row, index) => (
                      <div key={index} className="flex items-end gap-2">
                        <div className="flex flex-1 flex-col gap-1">
                          <span className="text-[11px] text-muted-foreground">{t("plans.edit.daysLabel")}</span>
                          <input
                            type="number"
                            min={1}
                            step="1"
                            value={row.days}
                            onChange={(event) => updateDuration(index, { days: event.target.value })}
                            className={fieldClassName}
                          />
                        </div>
                        <div className="flex flex-1 flex-col gap-1">
                          <span className="text-[11px] text-muted-foreground">{t("plans.edit.basePriceLabel")}</span>
                          <input
                            type="number"
                            min={0}
                            step="0.01"
                            value={row.base_price}
                            onChange={(event) => updateDuration(index, { base_price: event.target.value })}
                            className={fieldClassName}
                          />
                        </div>
                        <button
                          type="button"
                          onClick={() => removeDuration(index)}
                          aria-label={t("plans.edit.removeDuration")}
                          className="flex size-9 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-error/10 hover:text-error"
                        >
                          <Trash2 className="size-4" />
                        </button>
                      </div>
                    ))}
                    <motion.button
                      type="button"
                      onClick={addDuration}
                      {...bounceTap(bounceStrength)}
                      className="flex items-center justify-center gap-1.5 rounded-full border border-border px-3 py-1.5 text-[12.5px] font-medium text-foreground/90 transition-colors hover:bg-white/5"
                    >
                      <Plus className="size-3.5" />
                      {t("plans.edit.addDuration")}
                    </motion.button>
                  </div>
                )}
              </div>

              <div className="flex shrink-0 gap-2 border-t border-border px-5 py-4">
                <button
                  type="button"
                  onClick={onClose}
                  className="flex-1 rounded-full border border-border px-4 py-2 text-sm font-medium text-foreground/80 transition-colors hover:bg-white/5"
                >
                  {t("plans.edit.cancel")}
                </button>
                <motion.button
                  type="submit"
                  disabled={isSubmitting}
                  {...bounceTap(bounceStrength)}
                  className="flex-1 rounded-full bg-accent px-4 py-2 text-sm font-medium text-primary transition-colors hover:bg-primary/20 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {isSubmitting ? t("plans.edit.saving") : t("plans.edit.save")}
                </motion.button>
              </div>
            </form>
          </motion.div>
        </motion.div>
      </AnimatePresence>
    </DialogPortal>
  );
}
