import { TriangleAlert } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { listPlans } from "@entities/plans/api";
import { changeSubscriptionPlan, type SubscriptionListItem } from "@entities/subscriptions/api";
import { usePermissions } from "@entities/user/use-current-user";
import { durationDays } from "@features/subscription-grant/duration";
import type { DurationChoice } from "@features/subscription-grant/duration";
import { PlanDurationPicker } from "@features/subscription-grant/PlanDurationPicker";
import { getErrorMessage } from "@shared/api/http";
import { formatMoney } from "@shared/lib/format";
import { formatDate } from "@shared/lib/relative-time";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { Button } from "@shared/ui/Button";
import { Card } from "@shared/ui/Card";
import { ErrorState } from "@shared/ui/EmptyState";
import { KpiTile } from "@shared/ui/KpiTile";
import { Spinner } from "@shared/ui/Spinner";

interface SubscriptionPlanTabProps {
  subscription: SubscriptionListItem;
  onChanged: (updated: SubscriptionListItem) => void;
}

export function SubscriptionPlanTab({ subscription, onChanged }: SubscriptionPlanTabProps) {
  const { t, i18n } = useTranslation();
  const permissions = usePermissions();
  const canChange =
    permissions.includes("SUBSCRIPTIONS_PLAN_CHANGE") && permissions.includes("PLANS_VIEW") && subscription.status !== "DELETED";
  const [isEditing, setIsEditing] = useState(false);
  const snapshot = subscription.plan_snapshot;

  return (
    <div className="flex flex-col gap-3">
      <div className="grid grid-cols-3 gap-2">
        <KpiTile label={t("subscriptions.plan.name")} value={snapshot.name} />
        <KpiTile
          label={t("subscriptions.plan.price")}
          value={formatMoney(snapshot.price_paid, snapshot.currency, i18n.language, true)}
        />
        <KpiTile
          label={t("subscriptions.plan.duration")}
          value={t("subscriptions.duration.days", { count: snapshot.duration_days })}
        />
      </div>
      {canChange && !isEditing && (
        <Button variant="secondary" onClick={() => setIsEditing(true)}>
          {t("subscriptions.plan.change")}
        </Button>
      )}
      {isEditing && (
        <PlanChangeForm
          subscriptionId={subscription.id}
          keepLabel={t("subscriptions.duration.keep", { date: formatDate(subscription.expire_at, i18n.language) })}
          onChanged={(updated) => {
            setIsEditing(false);
            onChanged(updated);
          }}
          onCancel={() => setIsEditing(false)}
        />
      )}
    </div>
  );
}

interface PlanChangeFormProps {
  subscriptionId: number;
  keepLabel: string;
  onChanged: (updated: SubscriptionListItem) => void;
  onCancel: () => void;
}

function PlanChangeForm({ subscriptionId, keepLabel, onChanged, onCancel }: PlanChangeFormProps) {
  const { t } = useTranslation();
  const [plans] = useAsyncResource((signal) => listPlans(signal));
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
      const updated = await changeSubscriptionPlan(subscriptionId, { plan_id: planId, duration_days: days });
      toast.success(t("subscriptions.plan.changed"));
      onChanged(updated);
    } catch (err) {
      toast.error(getErrorMessage(err, t("subscriptions.plan.error")));
    } finally {
      setIsSubmitting(false);
    }
  };

  if (plans.kind === "loading") return <Spinner size="card" />;
  if (plans.kind === "error") return <ErrorState text={t("common.loadError")} />;

  return (
    <form onSubmit={(event) => void handleSubmit(event)}>
      <Card variant="form">
        <PlanDurationPicker
          plans={plans.data}
          planId={planId}
          onPlanChange={setPlanId}
          duration={duration}
          onDurationChange={setDuration}
          keepLabel={keepLabel}
        />
        <p className="flex items-start gap-2 rounded-2xl bg-warning/10 px-3 py-2.5 text-[12.5px] text-warning">
          <TriangleAlert className="mt-0.5 size-3.5 shrink-0" />
          {t("subscriptions.plan.resetWarning")}
        </p>
        <div className="flex justify-end gap-2">
          <Button variant="outline" type="button" onClick={onCancel}>
            {t("common.cancel")}
          </Button>
          <Button variant="accent" type="submit" disabled={isSubmitting || planId === null}>
            {t("subscriptions.plan.submit")}
          </Button>
        </div>
      </Card>
    </form>
  );
}
