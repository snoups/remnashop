import type { ParseKeys } from "i18next";
import { Receipt } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import type { RecentPayment, RevenueToday } from "@entities/overview/api";
import { useCanOpenUsers } from "@features/open-user/openable-user";
import { useOpenEntity } from "@shared/lib/entity-dialogs";
import { currencySymbol, formatMoney } from "@shared/lib/format";
import { formatTime } from "@shared/lib/relative-time";
import { Button } from "@shared/ui/Button";
import { EmptyState } from "@shared/ui/glass/EmptyState";
import { IconCircle } from "@shared/ui/glass/IconCircle";
import { Section } from "@shared/ui/glass/Section";
import { LIST_BODY_CLASS } from "@shared/ui/classes";
import { ListRow } from "@shared/ui/ListRow";

function formatPaidAt(iso: string, language: string): string {
  const date = new Date(iso);
  const today = new Date();
  const sameDay = date.toDateString() === today.toDateString();
  return sameDay
    ? formatTime(date, language)
    : date.toLocaleDateString(language, { day: "numeric", month: "short" });
}

export function RecentPaymentsCard({
  payments,
  revenue,
}: {
  payments: RecentPayment[];
  revenue: RevenueToday | null;
}) {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { openUser } = useOpenEntity();
  const canOpenUsers = useCanOpenUsers();
  const language = i18n.language;

  return (
    <Section
      icon={Receipt}
      title={t("dashboard.payments.title")}
      description={
        revenue ? t("dashboard.payments.description", { today: formatMoney(revenue.today, revenue.report_currency, language) }) : undefined
      }
      aside={
        <Button variant="glass" onClick={() => navigate("/dashboard/transactions")}>
          {t("dashboard.payments.all")}
        </Button>
      }
    >
      {payments.length === 0 ? (
        <EmptyState text={t("dashboard.payments.empty")} />
      ) : (
        <div className={`${LIST_BODY_CLASS} pt-4`}>
          {payments.map((payment) => (
            <ListRow
              key={payment.transaction_id}
              type="button"
              disabled={!canOpenUsers}
              onClick={() => openUser(payment.user_id)}
              className="grid grid-cols-[32px_minmax(0,1fr)_auto] items-center gap-3"
            >
              <IconCircle
                tone="success"
                glyph={<span className="text-sm font-bold">{currencySymbol(payment.currency)}</span>}
              />
              <span className="min-w-0">
                <span className="flex min-w-0 items-center gap-2">
                  <span className="truncate text-sm font-medium text-foreground">
                    {payment.plan_name}
                    {" · "}
                    {t("plans.daysShort", { count: payment.duration_days })}
                  </span>
                  <span className="shrink-0 font-mono text-xs text-muted-foreground">#{payment.transaction_id}</span>
                </span>
                <span className="flex min-w-0 gap-1 text-xs text-muted-foreground">
                  <span className="truncate">{payment.name || t("users.unnamed")}</span>
                  <span className="shrink-0 font-mono">#{payment.user_id}</span>
                  <span className="shrink-0">
                    &middot; {t(`settings.gateways.types.${payment.gateway_type}` as ParseKeys)}
                  </span>
                </span>
              </span>
              <span className="flex flex-col items-end tabular-nums">
                <span className="text-sm font-semibold text-foreground">
                  {formatMoney(payment.amount, payment.currency, language, true)}
                </span>
                <span className="whitespace-nowrap text-xs text-muted-foreground">
                  {t(`transactions.purchaseType.${payment.purchase_type}`)} &middot; {formatPaidAt(payment.paid_at, language)}
                </span>
              </span>
            </ListRow>
          ))}
        </div>
      )}
    </Section>
  );
}
