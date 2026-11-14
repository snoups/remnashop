import type { ParseKeys } from "i18next";
import { getTransaction, type TransactionItem } from "@entities/transactions/api";
import { usePermissions } from "@entities/user/use-current-user";
import { TransactionDetailsDialog } from "@features/transaction-details/TransactionDetailsDialog";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { ChevronDown, Filter, RefreshCw, Repeat } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { listRecurringPayments, manageRecurringPayment, type RecurringAction, type RecurringPaymentItem, type RecurringState } from "@entities/transactions/recurring-api";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { formatMoney } from "@shared/lib/format";
import { Badge, type BadgeTone } from "@shared/ui/Badge";
import { ErrorState, EmptyState } from "@shared/ui/glass/EmptyState";
import { SelectDropdown } from "@shared/ui/SelectDropdown";
import { Spinner } from "@shared/ui/Spinner";
import { Button } from "@shared/ui/Button";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";

const STATES: RecurringState[] = ["enabled", "disabled", "pending", "retrying", "attention"];
const TONES: Record<RecurringState, BadgeTone> = {
  enabled: "success", disabled: "neutral", pending: "warning", retrying: "accent", attention: "error",
};

function RecurringPaymentsContent() {
  const { t, i18n } = useTranslation();
  const permissions = usePermissions();
  const canViewOrder = permissions.includes("TRANSACTIONS_DETAIL_VIEW");
  const canManage = permissions.includes("TRANSACTIONS_RECURRING_MANAGE");
  const [acting, setActing] = useState<number | null>(null);
  const [closing, setClosing] = useState<RecurringPaymentItem | null>(null);
  const [detailsOrder, setDetailsOrder] = useState<TransactionItem | null>(null);
  const [openingOrder, setOpeningOrder] = useState<number | null>(null);
  const [filter, setFilter] = useState("");
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [appliedSearch, setAppliedSearch] = useState("");
  const [resource, reload] = useAsyncResource((signal) => listRecurringPayments(filter, page, appliedSearch, signal), {
    deps: [filter, page, appliedSearch], keepData: true,
  });
  const performAction = async (item: RecurringPaymentItem, action: RecurringAction) => {
    setActing(item.subscription_id);
    try {
      await manageRecurringPayment(item.subscription_id, action, item.pending_transaction_id);
      toast.success(t("transactions.recurring.actions.done"));
      reload();
    } catch (error) {
      toast.error(getErrorMessage(error, t("common.errors.generic")));
    } finally {
      setActing(null);
    }
  };
  const openOrder = async (orderId: number) => {
    setOpeningOrder(orderId);
    try {
      setDetailsOrder(await getTransaction(orderId));
    } catch (error) {
      toast.error(getErrorMessage(error, t("common.errors.generic")));
    } finally {
      setOpeningOrder(null);
    }
  };
  const date = (value: string | null) => value ? new Date(value).toLocaleString(i18n.language) : "—";
  const data = resource.kind === "ready" ? resource.data : null;
  const summary = data?.summary;
  const metrics = summary ? [
    [t("transactions.recurring.stats.total"), summary.total],
    [t("transactions.recurring.states.enabled"), summary.enabled],
    [t("transactions.recurring.states.pending"), summary.pending],
    [t("transactions.recurring.states.retrying"), summary.retrying],
    [t("transactions.recurring.states.attention"), summary.attention],
    [t("transactions.recurring.stats.paid"), summary.paid_renewals],
    [t("transactions.recurring.stats.failed"), summary.failed_renewals],
    [t("transactions.recurring.stats.revenue"), formatMoney(summary.revenue, summary.currency, i18n.language, true)],
  ] : [];
  return <div className="flex flex-col gap-4 p-4">
    <p className="text-xs text-muted-foreground">{t("transactions.recurring.description")}</p>
    <div className="flex flex-wrap items-center gap-3">
      <div className="w-64"><SelectDropdown id="recurring-state" value={filter} icon={Filter}
        size="compact" placeholder={t("transactions.recurring.all")}
        onChange={(value) => { setFilter(value); setPage(1); }}
        options={[{ value: "", label: t("transactions.recurring.all") },
          ...STATES.map((value) => ({ value, label: t(`transactions.recurring.states.${value}`) }))]} /></div>
      <form className="flex min-w-52 flex-1 items-center gap-2" onSubmit={(event) => {
        event.preventDefault(); setAppliedSearch(search.trim()); setPage(1);
      }}>
        <input type="search" value={search} onChange={(event) => setSearch(event.target.value)}
          aria-label={t("transactions.recurring.searchPlaceholder")} placeholder={t("transactions.recurring.searchPlaceholder")}
          maxLength={120} className="glass-well h-9 min-w-0 flex-1 rounded-lg px-3 text-sm outline-none focus:ring-1 focus:ring-primary" />
        <button type="submit" className="text-sm text-primary">{t("transactions.recurring.search")}</button>
      </form>
      <button type="button" onClick={reload} className="inline-flex items-center gap-2 text-sm text-primary">
        <RefreshCw className="size-4" />{t("transactions.recurring.refresh")}
      </button>
    </div>
    {resource.kind === "loading" && <div className="flex justify-center p-6"><Spinner /></div>}
    {resource.kind === "error" && <ErrorState text={t("transactions.recurring.error")} />}
    {summary && <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">{metrics.map(([label, value]) =>
      <div key={label} className="rounded-xl bg-white/[0.03] p-3">
        <div className="text-xs text-muted-foreground">{label}</div>
        <div className="mt-1 text-lg font-semibold tabular-nums">{value}</div>
      </div>)}</div>}
    {data && <>
      {data.items.length === 0 ? <EmptyState text={t("transactions.recurring.empty")} /> :
        <div className="overflow-x-auto"><table className="w-full text-left text-sm">
          <thead className="text-xs text-muted-foreground"><tr>
            <th className="p-2">{t("transactions.recurring.subscription")}</th>
            <th className="p-2">{t("transactions.recurring.state")}</th>
            <th className="p-2">{t("transactions.recurring.limit")}</th>
            <th className="p-2">{t("transactions.recurring.next")}</th>
            <th className="p-2">{t("transactions.recurring.errorReason")}</th>
          </tr></thead>
          <tbody>{data.items.map((item) => <tr key={item.subscription_id} className="border-t border-glass-border align-top">
            <td className="p-2"><div className="font-medium">{item.plan_name} · #{item.subscription_id}</div>
              <div className="text-xs text-muted-foreground">{item.user_name ?? "—"} · #{item.user_id}</div>
              <div className="text-xs text-muted-foreground">{t("transactions.recurring.expiry")}: {date(item.expire_at)}</div></td>
            <td className="p-2"><Badge tone={TONES[item.state]}>{t(`transactions.recurring.states.${item.state}`)}</Badge>
              {item.pending_transaction_id && <div className="mt-1 text-xs text-muted-foreground">
                {canViewOrder ? <button type="button" className="text-primary hover:underline disabled:opacity-40"
                  disabled={openingOrder !== null} onClick={() => void openOrder(item.pending_transaction_id!)}>
                  {t("transactions.recurring.order")}: #{item.pending_transaction_id}
                </button> : <span>{t("transactions.recurring.order")}: #{item.pending_transaction_id}</span>}
              </div>}
              {item.retry_count > 0 && <div className="mt-1 text-xs text-muted-foreground">{t("transactions.recurring.attempts")}: {item.retry_count}</div>}</td>
            <td className="whitespace-nowrap p-2 tabular-nums">{item.amount_limit && item.currency ? formatMoney(item.amount_limit, item.currency, i18n.language, true) : "—"}</td>
            <td className="whitespace-nowrap p-2 tabular-nums">{date(item.next_attempt_at)}</td>
            <td className="max-w-64 p-2 text-xs"><div>{item.last_error ? t(`transactions.recurring.reasons.${item.last_error}` as ParseKeys, { defaultValue: item.last_error }) : "—"}</div>
              {item.last_error && <code className="mt-1 block break-all text-muted-foreground">{item.last_error}</code>}
              {canManage && <div className="mt-2 flex flex-wrap gap-2">
                {item.can_check && <Button size="sm" variant="glass" disabled={acting !== null}
                  onClick={() => void performAction(item, "check")}>{t("transactions.recurring.actions.check")}</Button>}
                {item.can_close && <Button size="sm" variant="glassDanger" disabled={acting !== null}
                  onClick={() => setClosing(item)}>{t("transactions.recurring.actions.close")}</Button>}
                {item.can_retry && <Button size="sm" variant="glass" disabled={acting !== null}
                  onClick={() => void performAction(item, "retry")}>{t("transactions.recurring.actions.retry")}</Button>}
              </div>}
            </td>
          </tr>)}</tbody>
        </table></div>}
      <div className="flex items-center justify-end gap-4 text-sm">
        <span className="text-muted-foreground">{t("transactions.recurring.total", { count: data.total })}</span>
        <button type="button" disabled={page <= 1} onClick={() => setPage((value) => value - 1)} className="text-primary disabled:opacity-40">{t("transactions.recurring.previous")}</button>
        <span className="tabular-nums">{page}</span>
        <button type="button" disabled={page * data.page_size >= data.total} onClick={() => setPage((value) => value + 1)} className="text-primary disabled:opacity-40">{t("transactions.recurring.nextPage")}</button>
      </div>
    </>}
    {closing && <ConfirmDialog title={t("transactions.recurring.actions.closeTitle")}
      message={t("transactions.recurring.actions.closeMessage")}
      confirmLabel={t("transactions.recurring.actions.close")} cancelLabel={t("common.cancel")} danger
      onCancel={() => setClosing(null)} onConfirm={() => { const item = closing; setClosing(null); void performAction(item, "close"); }} />}
    {detailsOrder && <TransactionDetailsDialog order={detailsOrder} onClose={() => setDetailsOrder(null)}
      onChanged={(order) => { setDetailsOrder(order); reload(); }} />}
  </div>;
}

export function RecurringPaymentsPanel({ initiallyOpen = false }: { initiallyOpen?: boolean }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(initiallyOpen);
  return <section className="shrink-0 rounded-2xl border border-glass-border bg-white/[0.02]">
    <button type="button" onClick={() => setOpen((value) => !value)} aria-expanded={open}
      className="flex w-full items-center gap-3 p-4 text-left font-semibold">
      <Repeat className="size-4 text-primary" /><span className="flex-1">{t("transactions.recurring.title")}</span>
      <ChevronDown className={`size-4 transition-transform ${open ? "rotate-180" : ""}`} />
    </button>
    {open && <RecurringPaymentsContent />}
  </section>;
}
