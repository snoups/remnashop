import { Layers } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { OverviewSubscriptions } from "@entities/overview/api";
import { Section } from "@shared/ui/glass/Section";
import { EYEBROW_CLASS, KPI_VALUE_CLASS } from "@shared/ui/classes";

export function SubscriptionsCard({ subscriptions }: { subscriptions: OverviewSubscriptions }) {
  const { t, i18n } = useTranslation();
  const rows = [
    { key: "paid", value: subscriptions.paid_active, dot: "bg-primary" },
    { key: "trials", value: subscriptions.trials, dot: "bg-success" },
    { key: "limited", value: subscriptions.limited, dot: "bg-warning" },
    { key: "expiringSoon", value: subscriptions.expiring_soon, dot: "bg-error" },
    { key: "expired", value: subscriptions.expired, dot: "bg-muted-foreground" },
  ] as const;

  return (
    <Section
      icon={Layers}
      title={t("dashboard.subscriptions.title")}
      description={t("dashboard.subscriptions.description")}
    >
      <div className="flex flex-col gap-4 pt-4">
        <div className="flex items-baseline gap-2">
          <span className={`${KPI_VALUE_CLASS} text-foreground`}>{subscriptions.total.toLocaleString(i18n.language)}</span>
          <span className={EYEBROW_CLASS}>{t("dashboard.subscriptions.total")}</span>
        </div>
        <div className="flex flex-col gap-2.5">
          {rows.map((row) => (
            <div key={row.key} className="flex items-center justify-between gap-3 text-[13px]">
              <span className="flex items-center gap-2 text-muted-foreground">
                <span className={`size-2.5 rounded-full ${row.dot}`} />
                {t(`dashboard.subscriptions.${row.key}`)}
              </span>
              <span className="font-semibold tabular-nums text-foreground">
                {row.value.toLocaleString(i18n.language)}
              </span>
            </div>
          ))}
        </div>
      </div>
    </Section>
  );
}
