import {
  AtSign,
  CalendarDays,
  CircleCheck,
  CreditCard,
  Hash,
  KeyRound,
  Layers,
  Mail,
  Package,
  Percent,
  Receipt,
  Send,
  ShoppingCart,
  User,
  X,
} from "lucide-react";
import { useTranslation } from "react-i18next";

import { CURRENCY_SYMBOL, PAYMENT_STATUS_BADGE_CLASSNAME, type PaymentOrderItem } from "@entities/payments/api";
import { InfoRow } from "@shared/ui/InfoRow";
import { Modal, useModalClose } from "@shared/ui/Modal";

interface PaymentOrderDetailsDialogProps {
  order: PaymentOrderItem;
  onClose: () => void;
}

const sectionClassName = "rounded-2xl border border-white/[0.08] bg-white/[0.03] p-1.5";
const sectionTitleClassName =
  "px-2.5 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-wide text-foreground";

function DetailValue({ value, mono = false }: { value: string; mono?: boolean }) {
  return <span className={`max-w-60 truncate ${mono ? "text-[12px]" : "font-sans font-medium"}`}>{value}</span>;
}

export function PaymentOrderDetailsDialog({ order, onClose }: PaymentOrderDetailsDialogProps) {
  return (
    <Modal onClose={onClose} size="lg" scrollable>
      <PaymentOrderDetailsDialogBody order={order} />
    </Modal>
  );
}

function PaymentOrderDetailsDialogBody({ order }: { order: PaymentOrderItem }) {
  const { t } = useTranslation();
  const close = useModalClose();
  const symbol = CURRENCY_SYMBOL[order.currency] ?? order.currency;
  const gatewayLabel = t(`settings.gateways.types.${order.gateway_type}`);
  const statusLabel = t(`payments.status.${order.status}`);
  const none = t("payments.details.none");

  const plan = `${order.plan_snapshot.name ?? order.plan_snapshot.public_code ?? none} · ${order.duration_days}d`;
  const purchaseType = t(`payments.purchaseType.${order.purchase_type}`);
  const targetSubscription = order.target_subscription_id !== null ? `#${order.target_subscription_id}` : undefined;
  const createdAt = new Date(order.created_at).toLocaleString();
  const { user } = order;
  const username = user?.username ? `@${user.username}` : undefined;
  const telegramId = user !== null && user.telegram_id !== null ? String(user.telegram_id) : undefined;

  return (
    <>
      <div className="flex items-center justify-between gap-3 border-b border-border px-5 py-4">
        <div className="flex min-w-0 items-center gap-2.5">
          <div
            aria-hidden
            className="flex size-8 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] text-[13px] font-bold text-foreground backdrop-blur-md"
          >
            {symbol}
          </div>
          <h2 className="truncate text-base font-bold text-foreground">{t("payments.orderLabel", { id: order.id })}</h2>
        </div>
        <button
          type="button"
          onClick={close}
          aria-label={t("payments.details.close")}
          className="flex size-8 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-white/[0.06] hover:text-foreground"
        >
          <X className="size-4" />
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        <div className="flex flex-col gap-3">
          <section className="rounded-2xl border border-white/[0.08] bg-white/[0.03] px-4 pb-3.5 pt-1.5">
            <h3 className="pb-1 pt-2 text-[11px] font-semibold uppercase tracking-wide text-foreground">{t("payments.details.total")}</h3>
            <div className="mt-1 flex items-baseline gap-2.5">
              <span className="text-[28px] font-bold leading-none tracking-tight tabular-nums text-foreground">
                {symbol}
                {order.final_price}
              </span>
              {order.discount_percent > 0 && (
                <span className="text-[13px] tabular-nums text-muted-foreground line-through">
                  {symbol}
                  {order.base_price}
                </span>
              )}
            </div>
            {order.discount_percent > 0 && (
              <span className="mt-2.5 inline-flex items-center gap-1.5 rounded-full border border-primary/30 bg-accent px-2.5 py-0.5 text-[12px] font-medium text-accent-foreground">
                <Percent className="size-3" />
                {t("payments.details.discount", {
                  percent: order.discount_percent,
                  source: t(`payments.discountSource.${order.discount_source}`),
                })}
              </span>
            )}
          </section>

          <section className={sectionClassName}>
            <h3 className={sectionTitleClassName}>{t("payments.details.sections.purchase")}</h3>
            <InfoRow icon={Package} label={t("payments.details.plan")} copyValue={plan}>
              <DetailValue value={plan} />
            </InfoRow>
            <InfoRow icon={ShoppingCart} label={t("payments.details.purchaseType")} copyValue={purchaseType}>
              <DetailValue value={purchaseType} />
            </InfoRow>
            <InfoRow icon={Layers} label={t("payments.details.targetSubscription")} copyValue={targetSubscription}>
              <DetailValue value={targetSubscription ?? none} />
            </InfoRow>
            <InfoRow icon={CalendarDays} label={t("payments.details.createdAt")} copyValue={createdAt}>
              <DetailValue value={createdAt} />
            </InfoRow>
          </section>

          <section className={sectionClassName}>
            <h3 className={sectionTitleClassName}>{t("payments.details.sections.user")}</h3>
            <InfoRow icon={Hash} label={t("users.details.id")} copyValue={String(order.user_id)}>
              <DetailValue value={String(order.user_id)} />
            </InfoRow>
            <InfoRow icon={User} label={t("payments.details.name")} copyValue={user?.name}>
              <DetailValue value={user?.name ?? none} />
            </InfoRow>
            <InfoRow icon={Mail} label={t("users.details.email")} copyValue={user?.email ?? undefined}>
              <DetailValue value={user?.email ?? none} />
            </InfoRow>
            {telegramId !== undefined && (
              <div className="mt-1 rounded-xl border border-white/[0.06] bg-white/[0.02] p-1">
                <h4 className="flex items-center gap-1.5 px-2.5 pb-0.5 pt-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                  <Send className="size-3" />
                  {t("payments.details.sections.telegram")}
                </h4>
                <InfoRow icon={AtSign} label={t("users.details.username")} copyValue={username}>
                  <DetailValue value={username ?? none} />
                </InfoRow>
                <InfoRow icon={Hash} label={t("users.details.id")} copyValue={telegramId}>
                  <DetailValue value={telegramId} />
                </InfoRow>
              </div>
            )}
          </section>

          <section className={sectionClassName}>
            <h3 className={sectionTitleClassName}>{t("payments.details.sections.payment")}</h3>
            <InfoRow icon={Hash} label={t("payments.details.id")} copyValue={String(order.id)}>
              <DetailValue value={String(order.id)} />
            </InfoRow>
            <InfoRow icon={CircleCheck} label={t("payments.details.status")} copyValue={statusLabel}>
              <span
                className={`shrink-0 rounded-full border px-2 py-0.5 font-sans text-[10.5px] font-semibold uppercase tracking-wide ${PAYMENT_STATUS_BADGE_CLASSNAME[order.status]}`}
              >
                {statusLabel}
              </span>
            </InfoRow>
            <InfoRow icon={CreditCard} label={t("payments.details.gateway")} copyValue={gatewayLabel}>
              <DetailValue value={gatewayLabel} />
            </InfoRow>
            <InfoRow
              icon={Mail}
              label={t("payments.details.customerEmail")}
              copyValue={order.customer_email ?? undefined}
            >
              <DetailValue value={order.customer_email ?? none} />
            </InfoRow>
            <InfoRow
              icon={Receipt}
              label={t("payments.details.externalPaymentId")}
              copyValue={order.external_payment_id ?? undefined}
            >
              <DetailValue value={order.external_payment_id ?? none} mono />
            </InfoRow>
            <InfoRow icon={KeyRound} label={t("payments.details.idempotencyKey")} copyValue={order.idempotency_key}>
              <DetailValue value={order.idempotency_key} mono />
            </InfoRow>
          </section>
        </div>
      </div>

      <div className="flex items-center justify-end gap-2 border-t border-white/[0.07] px-5 py-4">
        <button
          type="button"
          onClick={close}
          className="rounded-full border border-border px-4 py-2 text-sm font-medium text-foreground/80 transition-colors hover:bg-white/5"
        >
          {t("payments.details.close")}
        </button>
      </div>
    </>
  );
}
