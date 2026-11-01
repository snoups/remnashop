import type { ParseKeys } from "i18next";
import { Receipt } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import type { RecentPayment, RevenueToday } from "@entities/overview/api";
import { useCanOpenUsers } from "@features/open-user/openable-user";
import { useOpenEntity } from "@shared/lib/entity-dialogs";
import { formatMoney } from "@shared/lib/format";
import { initials } from "@shared/lib/initials";
import { formatTime } from "@shared/lib/relative-time";
import { Badge } from "@shared/ui/Badge";
import { Button } from "@shared/ui/Button";
import { Card } from "@shared/ui/Card";
import { CardHeader } from "@shared/ui/CardHeader";
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
    <Card>
      <CardHeader
        icon={Receipt}
        title={t("dashboard.payments.title")}
        description={
          revenue ? t("dashboard.payments.description", { today: formatMoney(revenue.today, revenue.report_currency, language) }) : null
        }
        aside={
          <Button variant="secondary" size="sm" onClick={() => navigate("/dashboard/transactions")}>
            {t("dashboard.payments.all")}
          </Button>
        }
      />
      {payments.length === 0 ? (
        <p className="py-6 text-center text-[13px] text-muted-foreground">{t("dashboard.payments.empty")}</p>
      ) : (
        <div className={`${LIST_BODY_CLASS} pt-1.5`}>
          {payments.map((payment, index) => (
            <ListRow
              key={`${payment.user_id}-${payment.paid_at}-${index}`}
              type="button"
              disabled={!canOpenUsers}
              onClick={() => openUser(payment.user_id)}
              className={`grid grid-cols-[36px_minmax(0,1fr)_auto] items-center gap-3`}
            >
              <span className="flex size-9 items-center justify-center rounded-full bg-white/[0.06] text-[12px] font-bold text-foreground">
                {initials(payment.name)}
              </span>
              <span className="min-w-0">
                <span className="block truncate text-[13px] font-medium text-foreground">
                  {payment.name} · {payment.plan_name}
                </span>
                <span className="block truncate text-[12px] text-muted-foreground">
                  {t(`settings.gateways.types.${payment.gateway_type}` as ParseKeys, { defaultValue: payment.gateway_type })} ·{" "}
                  {formatPaidAt(payment.paid_at, language)}
                </span>
              </span>
              <span className="flex flex-col items-end gap-1">
                <span className="text-[13px] font-semibold tabular-nums text-foreground">
                  {formatMoney(payment.amount, payment.currency, language)}
                </span>
                <Badge tone="neutral">{t(`transactions.purchaseType.${payment.purchase_type}`)}</Badge>
              </span>
            </ListRow>
          ))}
        </div>
      )}
    </Card>
  );
}
