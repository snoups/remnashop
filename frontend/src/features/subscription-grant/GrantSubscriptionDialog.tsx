import { Captions } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { listPlans, type Plan } from "@entities/plans/api";
import { grantSubscription, type SubscriptionListItem } from "@entities/subscriptions/api";
import { defaultDuration, durationDays } from "@features/subscription-grant/duration";
import type { DurationChoice } from "@features/subscription-grant/duration";
import { PlanDurationPicker } from "@features/subscription-grant/PlanDurationPicker";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { Button } from "@shared/ui/Button";
import { GLASS_DIALOG_CARD_CLASS, GLASS_DIALOG_FOOTER_CLASS, GLASS_DIALOG_PAD_CLASS } from "@shared/ui/classes";
import { AnimatedHeight } from "@shared/ui/glass/AnimatedHeight";
import { DialogHeader } from "@shared/ui/glass/DialogHeader";
import { Modal } from "@shared/ui/Modal";
import { useModalClose } from "@shared/ui/modal-hooks";

interface GrantSubscriptionDialogProps {
  userId: number;
  onGranted: (subscription: SubscriptionListItem) => void;
  onClose: () => void;
}

// opens once the plans are in: the nested modal morphs to the size it has on mount, a spinner there
// would make it jump when the form arrives
export function GrantSubscriptionDialog({ onClose, ...props }: GrantSubscriptionDialogProps) {
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
      <GrantSubscriptionBody plans={plans.data} {...props} />
    </Modal>
  );
}

function GrantSubscriptionBody({ plans, userId, onGranted }: Omit<GrantSubscriptionDialogProps, "onClose"> & { plans: Plan[] }) {
  const { t } = useTranslation();
  const close = useModalClose();
  const [planId, setPlanId] = useState<number | null>(null);
  const [duration, setDuration] = useState<DurationChoice>({ kind: "custom", days: "" });
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handlePlanChange = (id: number) => {
    setPlanId(id);
    setDuration(defaultDuration(plans.find((plan) => plan.id === id)));
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const days = durationDays(duration);
    if (planId === null || !days) {
      toast.error(t("errors.invalidNumber"));
      return;
    }
    setIsSubmitting(true);
    try {
      const subscription = await grantSubscription({ user_id: userId, plan_id: planId, duration_days: days });
      toast.success(t("subscriptions.grant.done"));
      onGranted(subscription);
      close();
    } catch (err) {
      toast.error(getErrorMessage(err, t("subscriptions.grant.error")));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <>
      <DialogHeader icon={Captions} title={t("subscriptions.grant.title")} />
      <form onSubmit={(event) => void handleSubmit(event)} className="flex min-h-0 flex-1 flex-col">
        <div className={GLASS_DIALOG_PAD_CLASS}>
          {/* the custom-days field comes and goes */}
          <AnimatedHeight>
            <div className={GLASS_DIALOG_CARD_CLASS}>
              <PlanDurationPicker
                plans={plans}
                planId={planId}
                onPlanChange={handlePlanChange}
                duration={duration}
                onDurationChange={setDuration}
              />
            </div>
          </AnimatedHeight>
        </div>
        <div className={`${GLASS_DIALOG_FOOTER_CLASS} shrink-0 items-center justify-end`}>
          <Button variant="glass" type="button" onClick={close}>
            {t("common.cancel")}
          </Button>
          <Button variant="glassAccent" type="submit" disabled={planId === null} isLoading={isSubmitting}>
            {t("subscriptions.grant.submit")}
          </Button>
        </div>
      </form>
    </>
  );
}
