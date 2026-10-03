import type { ParseKeys } from "i18next";
import {
  AtSign,
  CalendarDays,
  CreditCard,
  Hash,
  KeyRound,
  Layers,
  Mail,
  Package,
  Receipt,
  Repeat,
  Send,
  ShoppingCart,
  User,
  Wallet,
} from "lucide-react";
import { useTranslation } from "react-i18next";

import { OpenUserFooter } from "@features/open-user/OpenUserFooter";
import { PAYMENT_STATUS_BADGE_TONE, type TransactionItem } from "@entities/transactions/api";
import { currencySymbol, formatMoney } from "@shared/lib/format";
import { formatDateTime } from "@shared/lib/relative-time";
import { InfoRow } from "@shared/ui/InfoRow";
import { Modal } from "@shared/ui/Modal";
import { DialogHeader } from "@shared/ui/DialogHeader";
import { Badge } from "@shared/ui/Badge";
import { Card } from "@shared/ui/Card";
import { KpiTile } from "@shared/ui/KpiTile";

interface TransactionDetailsDialogProps {
  order: TransactionItem;
  onClose: () => void;
}

const sectionTitleClassName =
  "flex items-center gap-1.5 px-2.5 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-wide text-foreground";

function DetailValue({ value }: { value: string }) {
  return <span className="max-w-60 truncate">{value}</span>;
}

export function TransactionDetailsDialog({ order, onClose }: TransactionDetailsDialogProps) {
  return (
    <Modal onClose={onClose} size="lg" scrollable>
      <TransactionDetailsDialogBody order={order} />
    </Modal>
  );
}

function TransactionDetailsDialogBody({ order }: { order: TransactionItem }) {
  const { t, i18n } = useTranslation();
  const money = (amount: string) => formatMoney(amount, order.currency, i18n.language, true);
  const symbol = currencySymbol(order.currency);
  const gatewayLabel = t(`settings.gateways.types.${order.gateway_type}` as ParseKeys);
  const statusLabel = t(`transactions.status.${order.status}`);
  const none = t("common.none");

  const plan = `${order.plan_snapshot.name ?? order.plan_snapshot.public_code ?? none} · ${t("plans.daysShort", { count: order.duration_days })}`;
  const purchaseType = t(`transactions.purchaseType.${order.purchase_type}`);
  const targetSubscription = order.target_subscription_id !== null ? `#${order.target_subscription_id}` : undefined;
  const createdAt = formatDateTime(order.created_at, i18n.language);
  const { user } = order;
  const username = user?.username ? `@${user.username}` : undefined;
  const telegramId = user !== null && user.telegram_id !== null ? String(user.telegram_id) : undefined;

  return (
    <>
      <DialogHeader
        glyph={<span className="text-[13px] font-bold">{symbol}</span>}
        title={t("transactions.orderLabel", { id: order.id })}
        badges={
          <Badge tone={PAYMENT_STATUS_BADGE_TONE[order.status]}>
            {statusLabel}
          </Badge>
        }
      />

      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        <div className="flex flex-col gap-3">
          <div className="grid grid-cols-2 gap-3">
            <KpiTile
              label={t("transactions.details.total")}
              value={money(order.final_price)}
              hint={
                order.discount_percent > 0
                  ? `${t("transactions.details.discount", {
                      percent: order.discount_percent,
                      source: t(`transactions.discountSource.${order.discount_source}`),
                    })} · ${t("transactions.details.basePrice", { price: money(order.base_price) })}`
                  : t("transactions.details.noDiscount")
              }
            />
            <KpiTile label={t("transactions.details.period")} value={t("plans.daysShort", { count: order.duration_days })} hint={purchaseType} />
          </div>

          <Card variant="list" title={t("transactions.details.sections.payment")} icon={Wallet}>
            <InfoRow icon={Hash} label={t("transactions.details.id")} copyValue={String(order.id)} mono>
              {order.id}
            </InfoRow>
            <InfoRow icon={CreditCard} label={t("transactions.details.gateway")} copyValue={gatewayLabel}>
              <DetailValue value={gatewayLabel} />
            </InfoRow>
            <InfoRow icon={CalendarDays} label={t("transactions.details.createdAt")} copyValue={createdAt} mono>
              <DetailValue value={createdAt} />
            </InfoRow>
            <InfoRow
              icon={Mail}
              label={t("transactions.details.customerEmail")}
              copyValue={order.customer_email ?? undefined}
              mono
            >
              <DetailValue value={order.customer_email ?? none} />
            </InfoRow>
            <InfoRow
              icon={Receipt}
              label={t("transactions.details.externalPaymentId")}
              copyValue={order.external_payment_id ?? undefined}
              mono
            >
              <DetailValue value={order.external_payment_id ?? none} />
            </InfoRow>
            <InfoRow icon={KeyRound} label={t("transactions.details.idempotencyKey")} copyValue={order.idempotency_key} mono>
              <DetailValue value={order.idempotency_key} />
            </InfoRow>
          </Card>

          <Card variant="list" title={t("transactions.details.sections.purchase")} icon={ShoppingCart}>
            <InfoRow icon={Repeat} label={t("transactions.details.purchaseType")} copyValue={purchaseType}>
              <DetailValue value={purchaseType} />
            </InfoRow>
            <InfoRow icon={Package} label={t("transactions.details.plan")} copyValue={plan}>
              <DetailValue value={plan} />
            </InfoRow>
            <InfoRow icon={Layers} label={t("transactions.details.targetSubscription")} copyValue={targetSubscription} mono>
              <DetailValue value={targetSubscription ?? none} />
            </InfoRow>
          </Card>

          <Card variant="list" title={t("transactions.details.sections.user")} icon={User}>
            <InfoRow icon={Hash} label={t("users.details.id")} copyValue={String(order.user_id)} mono>
              {order.user_id}
            </InfoRow>
            <InfoRow icon={User} label={t("transactions.details.name")} copyValue={user?.name || undefined}>
              <DetailValue value={user ? user.name || t("users.deleted.name") : none} />
            </InfoRow>
            <InfoRow icon={Mail} label={t("users.details.email")} copyValue={user?.email ?? undefined} mono>
              <DetailValue value={user?.email ?? none} />
            </InfoRow>
            {telegramId !== undefined && (
              <div className="m-1 rounded-xl border border-white/[0.06] bg-white/[0.02] p-1">
                <h4 className={sectionTitleClassName}>
                  <Send className="size-3.5" />
                  {t("transactions.details.sections.telegram")}
                </h4>
                <InfoRow icon={Hash} label={t("users.details.telegramId")} copyValue={telegramId} mono>
                  {telegramId}
                </InfoRow>
                <InfoRow icon={AtSign} label={t("users.details.username")} copyValue={username} mono>
                  <DetailValue value={username ?? none} />
                </InfoRow>
              </div>
            )}
          </Card>
        </div>
      </div>

      <OpenUserFooter
        links={[{ label: t("users.openUser"), icon: User, user: user && { id: order.user_id } }]}
      />
    </>
  );
}
