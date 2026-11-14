import { CalendarDays, Coins, Gauge, Gift, Globe, Hash, Network, Package, RefreshCw, Smartphone, Tag, Type, Wallet } from "lucide-react";
import { useTranslation } from "react-i18next";

import { formatLimit, formatTraffic, type SubscriptionListItem } from "@entities/subscriptions/api";
import { SubscriptionField } from "@features/subscription-edit/SubscriptionField";
import { useSquadName } from "@features/subscription-edit/use-squad-name";
import { formatDurationLong, isUnlimitedExpiry } from "@shared/lib/duration";
import { formatMoney } from "@shared/lib/format";
import { DialogCard } from "@shared/ui/glass/DialogCard";

interface SubscriptionPlanTabProps {
  subscription: SubscriptionListItem;
}

export function SubscriptionPlanTab({ subscription }: SubscriptionPlanTabProps) {
  const { t, i18n } = useTranslation();
  const squadName = useSquadName();
  const snapshot = subscription.plan_snapshot;
  const none = t("common.none");
  const unlimited = t("subscriptions.unlimited");
  // a free grant, trial or import stores a hardcoded 0 USD: no price, not a price of zero dollars
  const money = (amount: string) =>
    Number(amount) > 0 ? formatMoney(amount, snapshot.currency, i18n.language, true) : none;

  return (
    <div className="flex flex-col gap-3">
      <DialogCard title={t("subscriptions.plan.title")} icon={Package}>
        <SubscriptionField icon={Type} label={t("subscriptions.plan.name")} value={snapshot.name} />
        <SubscriptionField icon={Wallet} label={t("subscriptions.plan.price")} value={money(snapshot.price_paid)} />
        <SubscriptionField
          icon={CalendarDays}
          label={t("subscriptions.plan.duration")}
          value={
            // an import from the panel stores 0 with no term known: "forever" only when it is
            snapshot.duration_days === 0 && !isUnlimitedExpiry(subscription.expire_at)
              ? none
              : formatDurationLong(snapshot.duration_days, t)
          }
        />
        <SubscriptionField icon={Hash} label={t("subscriptions.plan.code")} value={snapshot.public_code} mono />
        {snapshot.credit_paid != null && snapshot.credit_days != null && (
          <SubscriptionField
            icon={Coins}
            label={t("subscriptions.plan.credit")}
            value={
              // an unlimited term's credit isn't counted in days
              snapshot.credit_days > 0
                ? `${money(snapshot.credit_paid)} · ${t("subscriptions.duration.days", { count: snapshot.credit_days })}`
                : money(snapshot.credit_paid)
            }
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
    </div>
  );
}
