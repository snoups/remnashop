import { CreditCard, X } from "lucide-react";
import { useTranslation } from "react-i18next";

import { CURRENCY_SYMBOL, type PaymentOrderItem } from "@entities/payments/api";
import { Modal, useModalClose } from "@shared/ui/Modal";

interface PaymentOrderDetailsDialogProps {
  order: PaymentOrderItem;
  onClose: () => void;
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 py-2">
      <span className="text-[12.5px] text-muted-foreground">{label}</span>
      <span className="truncate text-[13px] font-medium text-foreground">{value}</span>
    </div>
  );
}

export function PaymentOrderDetailsDialog({ order, onClose }: PaymentOrderDetailsDialogProps) {
  return (
    <Modal onClose={onClose} size="sm">
      <PaymentOrderDetailsDialogBody order={order} />
    </Modal>
  );
}

function PaymentOrderDetailsDialogBody({ order }: { order: PaymentOrderItem }) {
  const { t } = useTranslation();
  const close = useModalClose();
  const symbol = CURRENCY_SYMBOL[order.currency] ?? order.currency;
  const none = t("payments.details.none");

  return (
    <>
      <div className="flex items-center justify-between border-b border-border px-5 py-4">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-white/[0.06] text-foreground">
            <CreditCard className="size-4" />
          </div>
          <div className="min-w-0">
            <h2 className="truncate text-base font-bold text-foreground">
              {t("payments.orderLabel", { id: order.id })}
            </h2>
            <span className="truncate font-mono text-[12px] text-muted-foreground">
              {order.plan_snapshot.name ?? order.plan_snapshot.public_code ?? "—"}
            </span>
          </div>
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

      <div className="divide-y divide-border/50 px-5 pb-4 pt-1">
        <DetailRow label={t("payments.details.user")} value={`#${order.user_id}`} />
        <DetailRow label={t("payments.details.gateway")} value={t(`settings.gateways.types.${order.gateway_type}`)} />
        <DetailRow
          label={t("payments.details.purchaseType")}
          value={t(`payments.purchaseType.${order.purchase_type}`)}
        />
        <DetailRow
          label={t("payments.details.targetSubscription")}
          value={order.target_subscription_id !== null ? `#${order.target_subscription_id}` : none}
        />
        <DetailRow
          label={t("payments.details.discount")}
          value={
            order.discount_percent > 0
              ? `${order.discount_percent}% (${t(`payments.discountSource.${order.discount_source}`)})`
              : none
          }
        />
        <DetailRow label={t("payments.details.externalPaymentId")} value={order.external_payment_id ?? none} />
        <DetailRow label={t("payments.details.customerEmail")} value={order.customer_email ?? none} />
        <DetailRow label={t("payments.details.idempotencyKey")} value={order.idempotency_key} />
        <DetailRow label={t("payments.details.expiresAt")} value={new Date(order.expires_at).toLocaleString()} />
        <DetailRow label={t("payments.details.price")} value={`${symbol}${order.final_price}`} />
      </div>
    </>
  );
}
