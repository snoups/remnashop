import type { ParseKeys } from "i18next";
import {
  AtSign,
  CalendarDays,
  Captions,
  CreditCard,
  Hash,
  KeyRound,
  Mail,
  Package,
  PackageMinus,
  PackageCheck,
  Receipt,
  Repeat,
  SearchCheck,
  Send,
  ShoppingCart,
  Smartphone,
  Undo2,
  User,
  Wallet,
} from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { RefundDialog } from "@features/transaction-details/RefundDialog";
import { OpenUserFooter } from "@features/open-user/OpenUserFooter";
import {
  PAYMENT_STATUS_BADGE_TONE,
  type RefundPreview,
  type TransactionItem,
  canCheckTransactionPayment,
  canFulfillTransaction,
  canRefundTransaction,
  checkTransactionPayment,
  fulfillTransaction,
  getRefundPreview,
  hasDiscount,
  refundTransaction,
} from "@entities/transactions/api";
import { usePermissions } from "@entities/user/use-current-user";
import { userNameField } from "@entities/user/display";
import { getErrorMessage } from "@shared/api/http";
import { formatDuration } from "@shared/lib/duration";
import { toast } from "@shared/lib/toast";
import { currencySymbol, formatMoney } from "@shared/lib/format";
import { formatDateTime } from "@shared/lib/relative-time";
import { InfoRow } from "@shared/ui/InfoRow";
import { Modal } from "@shared/ui/Modal";
import { DialogHeader } from "@shared/ui/glass/DialogHeader";
import { DialogCard } from "@shared/ui/glass/DialogCard";
import { Badge } from "@shared/ui/Badge";
import { Button } from "@shared/ui/Button";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { KpiTile } from "@shared/ui/KpiTile";
import { GLASS_DIALOG_BODY_CLASS, SECTION_TITLE_CLASS } from "@shared/ui/classes";

interface TransactionDetailsDialogProps {
  order: TransactionItem;
  onClose: () => void;
  /** after a fulfill or refund, so the list behind can show the new status */
  onChanged?: (order: TransactionItem) => void;
}

function DetailValue({ value }: { value: string }) {
  return <span className="max-w-60 truncate">{value}</span>;
}

export function TransactionDetailsDialog({ order, onClose, onChanged }: TransactionDetailsDialogProps) {
  return (
    <Modal onClose={onClose} size="lg" scrollable>
      <TransactionDetailsDialogBody order={order} onChanged={onChanged} />
    </Modal>
  );
}

function TransactionDetailsDialogBody({
  order: initialOrder,
  onChanged,
}: Pick<TransactionDetailsDialogProps, "order" | "onChanged">) {
  const { t, i18n } = useTranslation();
  const [order, setOrder] = useState(initialOrder);
  const [isConfirmingFulfill, setIsConfirmingFulfill] = useState(false);
  const [isFulfilling, setIsFulfilling] = useState(false);
  const [isChecking, setIsChecking] = useState(false);
  const [refundPreview, setRefundPreview] = useState<RefundPreview | null>(null);
  const [isRefunding, setIsRefunding] = useState(false);
  const permissions = usePermissions();
  const canRefund =
    permissions.includes("TRANSACTIONS_REFUND") &&
    permissions.includes("TRANSACTIONS_REFUND_PREVIEW") &&
    canRefundTransaction(order);
  const canFulfill = permissions.includes("TRANSACTIONS_FULFILL") && canFulfillTransaction(order);
  const canCheckPayment = permissions.includes("TRANSACTIONS_PAYMENT_CHECK") && canCheckTransactionPayment(order);
  const money = (amount: string) => formatMoney(amount, order.currency, i18n.language, true);
  const symbol = currencySymbol(order.currency);
  const gatewayLabel = t(`settings.gateways.types.${order.gateway_type}` as ParseKeys);
  const statusLabel = t(`transactions.status.${order.status}`);
  const none = t("common.none");

  const handleFulfill = async () => {
    setIsFulfilling(true);
    try {
      const fulfilled = await fulfillTransaction(order.id);
      setOrder(fulfilled);
      onChanged?.(fulfilled);
      toast.success(t("transactions.fulfill.success"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("transactions.fulfill.error")));
    } finally {
      setIsFulfilling(false);
    }
  };

  const handleCheckPayment = async () => {
    setIsChecking(true);
    try {
      const result = await checkTransactionPayment(order.id);
      setOrder(result.transaction);
      onChanged?.(result.transaction);
      if (result.paid) toast.success(t("transactions.checkPayment.paid"));
      else toast.info(t("transactions.checkPayment.notPaid"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("transactions.checkPayment.error")));
    } finally {
      setIsChecking(false);
    }
  };

  const openRefund = async () => {
    setIsRefunding(true);
    try {
      setRefundPreview(await getRefundPreview(order.id));
    } catch (err) {
      toast.error(getErrorMessage(err, t("transactions.refund.error")));
    } finally {
      setIsRefunding(false);
    }
  };

  const handleRefund = async (rollbackSubscription: boolean) => {
    setRefundPreview(null);
    setIsRefunding(true);
    try {
      const result = await refundTransaction(order.id, rollbackSubscription);
      setOrder(result.transaction);
      onChanged?.(result.transaction);
      if (result.rollback_failed) toast.warning(t("transactions.refund.rollbackFailed"));
      else toast.success(t("transactions.refund.done"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("transactions.refund.error")));
    } finally {
      setIsRefunding(false);
    }
  };

  // what an unlimited subscription changed to another unlimited plan took off the price
  const hasCredit = Number(order.change_credit) > 0;
  // a test payment buys no term, and its 0 isn't "forever"
  const period = order.is_test ? none : formatDuration(order.duration_days, t);
  const plan = order.is_test ? order.plan_snapshot.name : `${order.plan_snapshot.name} · ${period}`;
  const previous = order.previous_plan_snapshot;
  // a panel import (plan 0) stores 0 days with no term known
  const previousPlan =
    previous &&
    [
      previous.name,
      previous.duration_days !== undefined && previous.plan_id !== 0 && formatDuration(previous.duration_days, t),
    ]
      .filter(Boolean)
      .join(" · ");
  const purchaseType = t(`transactions.purchaseType.${order.purchase_type}`);
  // what a renewal or change was for, otherwise what the order issued
  const subscriptionId = order.target_subscription_id ?? order.fulfilled_subscription_id;
  const targetSubscription = subscriptionId !== null ? `#${subscriptionId}` : undefined;
  const missingSubscription = order.status === "PAID" ? t("transactions.details.notIssued") : none;
  const createdAt = formatDateTime(order.created_at, i18n.language);
  const { user } = order;
  const username = user?.username ? `@${user.username}` : undefined;
  const telegramId = user !== null && user.telegram_id !== null ? String(user.telegram_id) : undefined;

  return (
    <>
      <DialogHeader
        glyph={<span className="text-sm font-bold">{symbol}</span>}
        title={t("transactions.orderLabel", { id: order.id })}
        subtitle={<span className="font-mono">{createdAt}</span>}
        actions={<Badge tone={PAYMENT_STATUS_BADGE_TONE[order.status]}>{statusLabel}</Badge>}
      />

      <div className={GLASS_DIALOG_BODY_CLASS}>
        <div className="flex flex-col gap-3">
          <div className="grid grid-cols-2 gap-3">
            <KpiTile
              glass
              label={t("transactions.details.total")}
              value={money(order.final_price)}
              valueSuffix={(hasDiscount(order) || hasCredit) && <s>{money(order.base_price)}</s>}
              hint={
                hasDiscount(order) || hasCredit
                  ? [
                      hasCredit && t("transactions.details.changeCredit", { amount: money(order.change_credit) }),
                      order.plan_discount_percent > 0 &&
                        t("transactions.details.planDiscount", { percent: order.plan_discount_percent }),
                      order.discount_percent > 0 &&
                        t("transactions.details.discount", {
                          percent: order.discount_percent,
                          source: t(`transactions.discountSource.${order.discount_source}`),
                        }),
                    ]
                      .filter(Boolean)
                      .join(" + ")
                  : t("transactions.details.noDiscount")
              }
            />
            <KpiTile glass label={t("transactions.details.period")} value={period} hint={purchaseType} />
          </div>

          <DialogCard title={t("transactions.details.sections.payment")} icon={Wallet}>
            <InfoRow icon={Hash} label={t("transactions.details.id")} copyValue={String(order.id)} mono>
              {order.id}
            </InfoRow>
            <InfoRow icon={CreditCard} label={t("transactions.details.gateway")} copyValue={gatewayLabel}>
              <DetailValue value={gatewayLabel} />
            </InfoRow>
            <InfoRow icon={Smartphone} label={t("transactions.details.channel")}>
              <DetailValue value={t(`transactions.channel.${order.channel}` as ParseKeys)} />
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
          </DialogCard>

          <DialogCard title={t("transactions.details.sections.purchase")} icon={ShoppingCart}>
            <InfoRow icon={Repeat} label={t("transactions.details.purchaseType")} copyValue={purchaseType}>
              <DetailValue value={purchaseType} />
            </InfoRow>
            {previousPlan && (
              <InfoRow icon={PackageMinus} label={t("transactions.details.previousPlan")} copyValue={previousPlan}>
                <DetailValue value={previousPlan} />
              </InfoRow>
            )}
            <InfoRow icon={Package} label={t("transactions.details.plan")} copyValue={plan}>
              <DetailValue value={plan} />
            </InfoRow>
            <InfoRow icon={Captions} label={t("transactions.details.targetSubscription")} copyValue={targetSubscription} mono>
              <DetailValue value={targetSubscription ?? missingSubscription} />
            </InfoRow>
          </DialogCard>

          <DialogCard title={t("transactions.details.sections.user")} icon={User}>
            <InfoRow icon={Hash} label={t("users.details.id")} copyValue={String(order.user_id)} mono>
              {order.user_id}
            </InfoRow>
            <InfoRow icon={User} label={t("transactions.details.name")} copyValue={user?.name || undefined}>
              <DetailValue value={user ? userNameField(user, t) : none} />
            </InfoRow>
            <InfoRow icon={Mail} label={t("users.details.email")} copyValue={user?.email ?? undefined} mono>
              <DetailValue value={user?.email ?? none} />
            </InfoRow>
            {telegramId !== undefined && (
              <div className="mt-1 rounded-md border border-white/[0.08] bg-white/[0.02] p-1">
                <h4 className={SECTION_TITLE_CLASS}>
                  <Send className="size-3.5" />
                  {t("transactions.details.sections.telegram")}
                </h4>
                <InfoRow icon={Send} label={t("users.details.telegramId")} copyValue={telegramId} mono>
                  {telegramId}
                </InfoRow>
                <InfoRow icon={AtSign} label={t("users.details.username")} copyValue={username} mono>
                  <DetailValue value={username ?? none} />
                </InfoRow>
              </div>
            )}
          </DialogCard>
        </div>
      </div>

      <OpenUserFooter
        links={[{ label: t("users.openUser"), icon: User, user: user && { id: order.user_id } }]}
      >
        {canRefund && (
          <Button variant="glassDanger" onClick={() => void openRefund()} isLoading={isRefunding}>
            <Undo2 className="size-4" />
            {t("transactions.refund.button")}
          </Button>
        )}
        {canCheckPayment && (
          <Button variant="glass" onClick={() => void handleCheckPayment()} isLoading={isChecking}>
            <SearchCheck className="size-4" />
            {t("transactions.checkPayment.action")}
          </Button>
        )}
        {canFulfill && (
          <Button variant="glassAccent" onClick={() => setIsConfirmingFulfill(true)} isLoading={isFulfilling}>
            <PackageCheck className="size-4" />
            {t("transactions.fulfill.action")}
          </Button>
        )}
      </OpenUserFooter>
      {refundPreview && (
        <RefundDialog
          order={order}
          preview={refundPreview}
          onConfirm={(rollback) => void handleRefund(rollback)}
          onCancel={() => setRefundPreview(null)}
        />
      )}
      {isConfirmingFulfill && (
        <ConfirmDialog
          title={t("transactions.fulfill.title")}
          message={
            order.status === "PAID"
              ? t("transactions.fulfill.confirm")
              : t("transactions.fulfill.confirmStatusChange", {
                  status: statusLabel,
                  paid: t("transactions.status.PAID"),
                })
          }
          confirmLabel={t("transactions.fulfill.action")}
          cancelLabel={t("common.cancel")}
          danger={order.status !== "PAID"}
          icon={PackageCheck}
          onConfirm={() => {
            setIsConfirmingFulfill(false);
            void handleFulfill();
          }}
          onCancel={() => setIsConfirmingFulfill(false)}
        />
      )}
    </>
  );
}
