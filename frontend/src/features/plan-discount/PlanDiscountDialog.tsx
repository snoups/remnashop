import { BadgePercent } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { type Plan, updatePlanDiscount } from "@entities/plans/api";
import { PLAN_DISCOUNT_STATUS_TONE, planDiscountStatus } from "@entities/plans/discount";
import { getErrorMessage } from "@shared/api/http";
import { isoToLastDay, lastDayToIso, startToIso, toIsoDate } from "@shared/lib/iso-date";
import { blockNonIntegerKeys } from "@shared/lib/number-input";
import { toast } from "@shared/lib/toast";
import { Badge } from "@shared/ui/Badge";
import { Button } from "@shared/ui/Button";
import { GLASS_DIALOG_CARD_CLASS } from "@shared/ui/classes";
import { DatePickerField } from "@shared/ui/DatePickerField";
import { DialogHeader } from "@shared/ui/glass/DialogHeader";
import { Field } from "@shared/ui/glass/Field";
import { Input } from "@shared/ui/glass/Input";
import { Modal } from "@shared/ui/Modal";
import { useModalClose } from "@shared/ui/modal-hooks";

interface PlanDiscountDialogProps {
  plan: Plan;
  onClose: () => void;
  onSaved: (plan: Plan) => void;
}

export function PlanDiscountDialog({ plan, onClose, onSaved }: PlanDiscountDialogProps) {
  return (
    <Modal onClose={onClose} size="lg">
      <PlanDiscountDialogBody plan={plan} onSaved={onSaved} />
    </Modal>
  );
}

function PlanDiscountDialogBody({ plan, onSaved }: Pick<PlanDiscountDialogProps, "plan" | "onSaved">) {
  const { t } = useTranslation();
  const close = useModalClose();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [percent, setPercent] = useState(String(plan.discount_percent));
  const [startsOn, setStartsOn] = useState(plan.discount_starts_at ? toIsoDate(new Date(plan.discount_starts_at)) : "");
  const [lastDay, setLastDay] = useState(isoToLastDay(plan.discount_ends_at));

  const startsAt = startToIso(startsOn);
  const endsAt = lastDayToIso(lastDay);
  const percentValue = Number(percent);
  const isPercentInvalid = !Number.isInteger(percentValue) || percentValue < 0 || percentValue > 100;
  const isWindowInvalid = startsAt !== null && endsAt !== null && startsAt >= endsAt;
  const status = planDiscountStatus({
    ...plan,
    discount_percent: isPercentInvalid ? 0 : percentValue,
    discount_starts_at: startsAt,
    discount_ends_at: endsAt,
  });

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (isPercentInvalid || isWindowInvalid) return;
    setIsSubmitting(true);
    try {
      const updated = await updatePlanDiscount(plan.id, {
        discount_percent: percentValue,
        discount_starts_at: startsAt,
        discount_ends_at: endsAt,
      });
      toast.success(t("plans.discount.saved"));
      onSaved(updated);
      close();
    } catch (err) {
      toast.error(getErrorMessage(err, t("plans.discount.error")));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <>
      <DialogHeader icon={BadgePercent} title={t("plans.discount.title")} subtitle={plan.name} />

      <form onSubmit={(event) => void handleSubmit(event)} className="flex min-h-0 flex-1 flex-col">
        <div className="flex flex-col gap-3 p-3 [--dialog-pad:0.75rem]">
          <div className={GLASS_DIALOG_CARD_CLASS}>
            <Field label={t("plans.discount.percentLabel")} htmlFor="plan-discount-percent" hint={t("plans.discount.percentHint")}>
              <Input
                id="plan-discount-percent"
                type="number"
                min={0}
                max={100}
                step="1"
                onKeyDown={blockNonIntegerKeys}
                suffix="%"
                value={percent}
                aria-invalid={isPercentInvalid}
                onChange={(event) => setPercent(event.target.value)}
              />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label={t("plans.discount.startsLabel")} htmlFor="plan-discount-starts">
                <DatePickerField
                  compact
                  id="plan-discount-starts"
                  value={startsOn}
                  onChange={setStartsOn}
                  placeholder={t("plans.discount.startsPlaceholder")}
                />
              </Field>
              <Field
                label={t("plans.discount.endsLabel")}
                htmlFor="plan-discount-ends"
                error={isWindowInvalid ? t("apiErrors.PLAN_DISCOUNT_WINDOW_INVALID") : undefined}
              >
                <DatePickerField
                  compact
                  id="plan-discount-ends"
                  value={lastDay}
                  onChange={setLastDay}
                  placeholder={t("plans.discount.endsPlaceholder")}
                />
              </Field>
            </div>
            <p className="text-[12px] text-muted-foreground">{t("plans.discount.stackingHint")}</p>
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-2 border-t border-white/[0.08] p-4">
          <div className="min-w-0 flex-1">
            {status && (
              <Badge borderless tone={PLAN_DISCOUNT_STATUS_TONE[status]}>{t(`plans.discount.status.${status}`)}</Badge>
            )}
          </div>
          <Button variant="glass" type="button" onClick={close}>
            {t("common.cancel")}
          </Button>
          <Button variant="glassAccent" type="submit" disabled={isPercentInvalid || isWindowInvalid} isLoading={isSubmitting}>
            {t("common.save")}
          </Button>
        </div>
      </form>
    </>
  );
}
