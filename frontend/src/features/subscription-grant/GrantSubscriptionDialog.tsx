import { Gift } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { listPlans } from "@entities/plans/api";
import { grantSubscription, type SubscriptionListItem } from "@entities/subscriptions/api";
import { defaultDuration, durationDays } from "@features/subscription-grant/duration";
import type { DurationChoice } from "@features/subscription-grant/duration";
import { PlanDurationPicker } from "@features/subscription-grant/PlanDurationPicker";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { Button } from "@shared/ui/Button";
import { Card } from "@shared/ui/Card";
import { DialogHeader } from "@shared/ui/DialogHeader";
import { ErrorState } from "@shared/ui/EmptyState";
import { Modal } from "@shared/ui/Modal";
import { useModalClose } from "@shared/ui/modal-hooks";
import { Spinner } from "@shared/ui/Spinner";

interface GrantSubscriptionDialogProps {
  userId: number;
  onGranted: (subscription: SubscriptionListItem) => void;
  onClose: () => void;
}

export function GrantSubscriptionDialog({ onClose, ...props }: GrantSubscriptionDialogProps) {
  return (
    <Modal onClose={onClose} size="md">
      <GrantSubscriptionBody {...props} />
    </Modal>
  );
}

function GrantSubscriptionBody({ userId, onGranted }: Omit<GrantSubscriptionDialogProps, "onClose">) {
  const { t } = useTranslation();
  const close = useModalClose();
  const [plans] = useAsyncResource((signal) => listPlans(signal));
  const [planId, setPlanId] = useState<number | null>(null);
  const [duration, setDuration] = useState<DurationChoice>({ kind: "custom", days: "" });
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handlePlanChange = (id: number) => {
    setPlanId(id);
    setDuration(defaultDuration(plans.kind === "ready" ? plans.data.find((plan) => plan.id === id) : undefined));
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
      <DialogHeader icon={Gift} tone="primary" title={t("subscriptions.grant.title")} />
      <form onSubmit={(event) => void handleSubmit(event)} className="flex min-h-0 flex-1 flex-col">
        <div className="flex flex-col gap-3 px-4 pb-4">
          {plans.kind === "loading" && <Spinner size="card" />}
          {plans.kind === "error" && <ErrorState text={t("plans.loadError")} />}
          {plans.kind === "ready" && (
            <Card variant="form">
              <PlanDurationPicker
                plans={plans.data}
                planId={planId}
                onPlanChange={handlePlanChange}
                duration={duration}
                onDurationChange={setDuration}
              />
            </Card>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-2 border-t border-white/[0.07] px-5 py-3.5">
          <span className="flex-1" />
          <Button variant="outline" type="button" onClick={close}>
            {t("common.cancel")}
          </Button>
          <Button variant="accent" type="submit" disabled={isSubmitting || planId === null}>
            {t("subscriptions.grant.submit")}
          </Button>
        </div>
      </form>
    </>
  );
}
