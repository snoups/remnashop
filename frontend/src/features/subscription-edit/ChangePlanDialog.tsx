import { Replace, TriangleAlert } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { listPlans, type Plan } from "@entities/plans/api";
import { changeSubscriptionPlan, type SubscriptionListItem } from "@entities/subscriptions/api";
import { durationDays } from "@features/subscription-grant/duration";
import type { DurationChoice } from "@features/subscription-grant/duration";
import { PlanDurationPicker } from "@features/subscription-grant/PlanDurationPicker";
import { getErrorMessage } from "@shared/api/http";
import { formatDate } from "@shared/lib/relative-time";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { Button } from "@shared/ui/Button";
import { GLASS_DIALOG_CARD_CLASS, GLASS_DIALOG_FOOTER_CLASS } from "@shared/ui/classes";
import { AnimatedHeight } from "@shared/ui/glass/AnimatedHeight";
import { DialogHeader } from "@shared/ui/glass/DialogHeader";
import { Modal } from "@shared/ui/Modal";
import { useModalClose } from "@shared/ui/modal-hooks";

interface ChangePlanDialogProps {
  subscription: SubscriptionListItem;
  onChanged: (updated: SubscriptionListItem) => void;
  onClose: () => void;
}

// opens once the plans are in: the nested modal morphs to the size it has on mount, a spinner there
// would make it jump when the form arrives
export function ChangePlanDialog({ onClose, ...props }: ChangePlanDialogProps) {
  const { t } = useTranslation();
  const [plans] = useAsyncResource((signal) => listPlans(signal));
  const failed = plans.kind === "error";
  useEffect(() => {
    if (!failed) return;
    toast.error(t("common.loadError"));
    onClose();
  }, [failed, onClose, t]);

  if (plans.kind !== "ready") return null;
  return (
    <Modal onClose={onClose} size="md">
      <ChangePlanBody plans={plans.data} {...props} />
    </Modal>
  );
}

function ChangePlanBody({ plans, subscription, onChanged }: Omit<ChangePlanDialogProps, "onClose"> & { plans: Plan[] }) {
  const { t, i18n } = useTranslation();
  const close = useModalClose();
  const [planId, setPlanId] = useState<number | null>(null);
  const [duration, setDuration] = useState<DurationChoice>({ kind: "keep" });
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const days = durationDays(duration);
    if (planId === null || days === undefined) {
      toast.error(t("errors.invalidNumber"));
      return;
    }
    setIsSubmitting(true);
    try {
      const updated = await changeSubscriptionPlan(subscription.id, { plan_id: planId, duration_days: days });
      toast.success(t("subscriptions.plan.changed"));
      onChanged(updated);
      close();
    } catch (err) {
      toast.error(getErrorMessage(err, t("subscriptions.plan.error")));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <>
      <DialogHeader icon={Replace} title={t("subscriptions.plan.change")} subtitle={
          <span className="flex min-w-0 gap-1">
            <span className="truncate">{subscription.plan_snapshot.name}</span>
            <span className="shrink-0">#{subscription.id}</span>
          </span>
        }
      />
      <form onSubmit={(event) => void handleSubmit(event)} className="flex min-h-0 flex-1 flex-col">
        <div className="p-3 [--dialog-pad:0.75rem]">
          {/* the custom-days field comes and goes */}
          <AnimatedHeight>
            <div className={GLASS_DIALOG_CARD_CLASS}>
              <PlanDurationPicker
                plans={plans}
                planId={planId}
                onPlanChange={setPlanId}
                duration={duration}
                onDurationChange={setDuration}
                keepLabel={t("subscriptions.duration.keep", { date: formatDate(subscription.expire_at, i18n.language) })}
              />
              <p className="flex items-start gap-2 rounded-xl bg-warning/10 px-3 py-2.5 text-xs text-warning">
                <TriangleAlert className="mt-0.5 size-3.5 shrink-0" />
                {t("subscriptions.plan.resetWarning")}
              </p>
            </div>
          </AnimatedHeight>
        </div>
        <div className={`${GLASS_DIALOG_FOOTER_CLASS} shrink-0 items-center justify-end`}>
          <Button variant="glass" type="button" onClick={close}>
            {t("common.cancel")}
          </Button>
          <Button variant="glassAccent" type="submit" disabled={planId === null} isLoading={isSubmitting}>
            {t("subscriptions.plan.submit")}
          </Button>
        </div>
      </form>
    </>
  );
}
