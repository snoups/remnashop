import { CreditCard, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useTranslation } from "react-i18next";

import { CURRENCY_SYMBOL, type PaymentOrderItem } from "@entities/payments/api";
import { DialogPortal } from "@shared/ui/DialogPortal";

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
  const { t } = useTranslation();
  const symbol = CURRENCY_SYMBOL[order.currency] ?? order.currency;
  const none = t("payments.details.none");

  return (
    <DialogPortal>
      <AnimatePresence>
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15, ease: "easeOut" }}
          className="fixed inset-0 z-40 flex items-center justify-center bg-black/55 backdrop-blur-3xl p-4"
        >
          <button
            type="button"
            aria-hidden
            tabIndex={-1}
            className="absolute inset-0 cursor-default"
            onClick={onClose}
          />

          <motion.div
            initial={{ opacity: 0, scale: 0.94, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.94, y: 8 }}
            transition={{ duration: 0.18, ease: "easeOut" }}
            className="relative z-50 w-full max-w-sm rounded-dialog border border-white/[0.14] bg-popover/60 shadow-[0_24px_48px_-20px_rgba(4,8,20,0.6),inset_0_1px_0_rgba(232,236,251,0.16)] backdrop-blur-2xl backdrop-saturate-150"
          >
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
                onClick={onClose}
                aria-label={t("payments.details.close")}
                className="flex size-8 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-white/[0.06] hover:text-foreground"
              >
                <X className="size-4" />
              </button>
            </div>

            <div className="divide-y divide-border/50 px-5 pb-4 pt-1">
              <DetailRow label={t("payments.details.user")} value={`#${order.user_id}`} />
              <DetailRow label={t("payments.details.gateway")} value={t(`settings.gateways.types.${order.gateway_type}`)} />
              <DetailRow label={t("payments.details.purchaseType")} value={t(`payments.purchaseType.${order.purchase_type}`)} />
              <DetailRow
                label={t("payments.details.targetSubscription")}
                value={order.target_subscription_id !== null ? `#${order.target_subscription_id}` : none}
              />
              <DetailRow
                label={t("payments.details.discount")}
                value={order.discount_percent > 0 ? `${order.discount_percent}% (${t(`payments.discountSource.${order.discount_source}`)})` : none}
              />
              <DetailRow
                label={t("payments.details.externalPaymentId")}
                value={order.external_payment_id ?? none}
              />
              <DetailRow label={t("payments.details.customerEmail")} value={order.customer_email ?? none} />
              <DetailRow label={t("payments.details.idempotencyKey")} value={order.idempotency_key} />
              <DetailRow
                label={t("payments.details.expiresAt")}
                value={new Date(order.expires_at).toLocaleString()}
              />
              <DetailRow label={t("payments.details.price")} value={`${symbol}${order.final_price}`} />
            </div>
          </motion.div>
        </motion.div>
      </AnimatePresence>
    </DialogPortal>
  );
}
