import { BadgePercent } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { type Plan, updatePlanDiscount } from "@entities/plans/api";
import { PLAN_DISCOUNT_STATUS_TONE, planDiscountStatus } from "@entities/plans/discount";
import { getErrorMessage } from "@shared/api/http";
import { parseIsoDate, toIsoDate } from "@shared/lib/iso-date";
import { blockNonIntegerKeys } from "@shared/lib/number-input";
import { toast } from "@shared/lib/toast";
import { Badge } from "@shared/ui/Badge";
import { Button } from "@shared/ui/Button";
import { Card } from "@shared/ui/Card";
import { DatePickerField } from "@shared/ui/DatePickerField";
import { DialogHeader } from "@shared/ui/DialogHeader";
import { Field } from "@shared/ui/Field";
import { Modal } from "@shared/ui/Modal";
import { useModalClose } from "@shared/ui/modal-hooks";
import { SuffixInput } from "@shared/ui/TextInput";

interface PlanDiscountDialogProps {
  plan: Plan;
  onClose: () => void;
  onSaved: (plan: Plan) => void;
}

// both bounds are local midnights; the end one is the day after the picked last day
function startToIso(day: string): string | null {
  return parseIsoDate(day)?.toISOString() ?? null;
}

function lastDayToIso(day: string): string | null {
  const date = parseIsoDate(day);
  if (!date) return null;
  date.setDate(date.getDate() + 1);
  return date.toISOString();
}

function isoToLastDay(iso: string | null): string {
  return iso ? toIsoDate(new Date(new Date(iso).getTime() - 1)) : "";
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
        <div className="flex flex-col gap-3 p-4">
          <Card variant="form">
            <Field label={t("plans.discount.percentLabel")} htmlFor="plan-discount-percent" hint={t("plans.discount.percentHint")}>
              <SuffixInput
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
                  variant="form"
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
                  variant="form"
                  id="plan-discount-ends"
                  value={lastDay}
                  onChange={setLastDay}
                  placeholder={t("plans.discount.endsPlaceholder")}
                />
              </Field>
            </div>
            <p className="text-[12px] text-muted-foreground">{t("plans.discount.stackingHint")}</p>
          </Card>
        </div>

        <div className="flex shrink-0 items-center gap-2 border-t border-white/[0.07] px-5 py-3.5">
          <div className="min-w-0 flex-1">
            {status && (
              <Badge tone={PLAN_DISCOUNT_STATUS_TONE[status]}>{t(`plans.discount.status.${status}`)}</Badge>
            )}
          </div>
          <Button variant="outline" type="button" onClick={close}>
            {t("common.cancel")}
          </Button>
          <Button variant="accent" type="submit" disabled={isSubmitting || isPercentInvalid || isWindowInvalid}>
            {isSubmitting ? t("common.saving") : t("common.save")}
          </Button>
        </div>
      </form>
    </>
  );
}
