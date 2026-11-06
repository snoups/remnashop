import {
  Coins,
  Gauge,
  Gift,
  Globe,
  Hash,
  Network,
  Package,
  RefreshCw,
  Smartphone,
  Tag,
  TriangleAlert,
} from "lucide-react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { listPlans } from "@entities/plans/api";
import { changeSubscriptionPlan, formatLimit, formatTraffic, type SubscriptionListItem } from "@entities/subscriptions/api";
import { useAccountPermissions } from "@entities/user/use-current-user";
import { SubscriptionField } from "@features/subscription-edit/SubscriptionField";
import { useSquadName } from "@features/subscription-edit/use-squad-name";
import { durationDays } from "@features/subscription-grant/duration";
import type { DurationChoice } from "@features/subscription-grant/duration";
import { PlanDurationPicker } from "@features/subscription-grant/PlanDurationPicker";
import { getErrorMessage } from "@shared/api/http";
import { formatMoney } from "@shared/lib/format";
import { formatDate } from "@shared/lib/relative-time";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { Button } from "@shared/ui/Button";
import { GLASS_DIALOG_CARD_CLASS } from "@shared/ui/classes";
import { DialogCard } from "@shared/ui/glass/DialogCard";
import { ErrorState } from "@shared/ui/glass/EmptyState";
import { KpiTile } from "@shared/ui/KpiTile";
import { Spinner } from "@shared/ui/Spinner";

interface SubscriptionPlanTabProps {
  subscription: SubscriptionListItem;
  onChanged: (updated: SubscriptionListItem) => void;
}

export function SubscriptionPlanTab({ subscription, onChanged }: SubscriptionPlanTabProps) {
  const { t, i18n } = useTranslation();
  const permissions = useAccountPermissions(subscription.user_id);
  const canChange =
    permissions.includes("SUBSCRIPTIONS_PLAN_CHANGE") && permissions.includes("PLANS_VIEW") && subscription.status !== "DELETED";
  const [isEditing, setIsEditing] = useState(false);
  const squadName = useSquadName();
  const snapshot = subscription.plan_snapshot;
  const none = t("common.none");
  const unlimited = t("subscriptions.unlimited");
  // a free grant, trial or import stores a hardcoded 0 USD: no price, not a price of zero dollars
  const money = (amount: string) =>
    Number(amount) > 0 ? formatMoney(amount, snapshot.currency, i18n.language, true) : none;

  return (
    <div className="flex flex-col gap-3">
      <div className="grid grid-cols-3 gap-3">
        <KpiTile glass label={t("subscriptions.plan.name")} value={snapshot.name} />
        <KpiTile glass label={t("subscriptions.plan.price")} value={money(snapshot.price_paid)} />
        <KpiTile
          glass
          label={t("subscriptions.plan.duration")}
          value={t("subscriptions.duration.days", { count: snapshot.duration_days })}
        />
      </div>
      <DialogCard title={t("subscriptions.plan.title")} icon={Package}>
        <SubscriptionField icon={Hash} label={t("subscriptions.plan.code")} value={snapshot.public_code} mono />
        {snapshot.credit_paid != null && snapshot.credit_days != null && (
          <SubscriptionField
            icon={Coins}
            label={t("subscriptions.plan.credit")}
            value={`${money(snapshot.credit_paid)} · ${t("subscriptions.duration.days", { count: snapshot.credit_days })}`}
          />
        )}
        <SubscriptionField
          icon={Gift}
          label={t("subscriptions.plan.trial")}
          value={snapshot.is_trial ? t("common.yes") : t("common.no")}
        />
        <SubscriptionField
          icon={Gauge}
          label={t("subscriptions.fields.traffic")}
          value={formatTraffic(snapshot.traffic_limit, unlimited)}
        />
        <SubscriptionField
          icon={Smartphone}
          label={t("subscriptions.fields.devices")}
          value={formatLimit(snapshot.device_limit, unlimited)}
        />
        <SubscriptionField
          icon={RefreshCw}
          label={t("subscriptions.edit.strategyLabel")}
          value={t(`subscriptions.edit.strategy.${snapshot.traffic_limit_strategy}`)}
        />
        <SubscriptionField icon={Tag} label={t("subscriptions.edit.tagLabel")} value={snapshot.tag} />
        <SubscriptionField
          icon={Network}
          label={t("subscriptions.details.internalSquads")}
          value={snapshot.internal_squads.map(squadName).join(", ")}
          copyValue={snapshot.internal_squads.join(", ")}
        />
        <SubscriptionField
          icon={Globe}
          label={t("subscriptions.details.externalSquad")}
          value={snapshot.external_squad && squadName(snapshot.external_squad)}
          copyValue={snapshot.external_squad}
        />
      </DialogCard>
      {canChange && !isEditing && (
        <Button variant="glass" onClick={() => setIsEditing(true)}>
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
      <div className={GLASS_DIALOG_CARD_CLASS}>
        <PlanDurationPicker
          plans={plans.data}
          planId={planId}
          onPlanChange={setPlanId}
          duration={duration}
          onDurationChange={setDuration}
          keepLabel={keepLabel}
        />
        <p className="flex items-start gap-2 rounded-xl bg-warning/10 px-3 py-2.5 text-[12px] text-warning">
          <TriangleAlert className="mt-0.5 size-3.5 shrink-0" />
          {t("subscriptions.plan.resetWarning")}
        </p>
        <div className="flex justify-end gap-2">
          <Button variant="glass" type="button" onClick={onCancel}>
            {t("common.cancel")}
          </Button>
          <Button variant="glassAccent" type="submit" disabled={planId === null} isLoading={isSubmitting}>
            {t("subscriptions.plan.submit")}
          </Button>
        </div>
      </div>
    </form>
  );
}
