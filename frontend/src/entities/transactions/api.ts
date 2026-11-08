import { DollarSign, RussianRuble, Star, type LucideIcon } from "lucide-react";

import type { PlanSnapshot } from "@entities/subscriptions/api";
import { apiGet, apiPost } from "@shared/api/http";
import type { ListResponse } from "@shared/api/http";
import type { BadgeTone } from "@shared/ui/Badge";

export type TransactionStatus = "PENDING" | "PAID" | "FAILED" | "CANCELED" | "REFUNDED";
export type PurchaseType = "NEW" | "RENEW" | "CHANGE";
export type DiscountSource = "NONE" | "PERSONAL" | "PURCHASE" | "LOYALTY";

export interface TransactionUser {
  name: string;
  username: string | null;
  telegram_id: number | null;
  email: string | null;
}

export interface TransactionItem {
  id: number;
  user_id: number;
  /** null once the user is deleted */
  user: TransactionUser | null;
  plan_id: number | null;
  plan_snapshot: PlanSnapshot;
  /** a CHANGE order's plan before it; null on other orders and older ones */
  previous_plan_snapshot: PlanSnapshot | null;
  duration_days: number;
  currency: string;
  purchase_type: PurchaseType;
  target_subscription_id: number | null;
  /** the subscription the order provisioned, once reconciled */
  fulfilled_subscription_id: number | null;
  gateway_type: string;
  channel: "BOT" | "CABINET";
  external_payment_id: string | null;
  status: TransactionStatus;
  base_price: string;
  discount_percent: number;
  discount_source: DiscountSource;
  plan_discount_percent: number;
  final_price: string;
  customer_email: string | null;
  idempotency_key: string;
  is_test: boolean;
  expires_at: string;
  created_at: string;
}

export function hasDiscount(order: TransactionItem): boolean {
  return order.discount_percent > 0 || order.plan_discount_percent > 0;
}

// the plan's and the user's discounts are applied one after the other
export function totalDiscountPercent(order: TransactionItem): number {
  return Math.round(100 - ((100 - order.plan_discount_percent) * (100 - order.discount_percent)) / 100);
}

export const DEFAULT_PAGE_SIZE = 50;

export interface TransactionListPage {
  items: TransactionItem[];
  total: number;
}

export interface TransactionListFilters {
  status?: TransactionStatus;
  gatewayType?: string;
  purchaseType?: PurchaseType;
  createdFrom?: string;
  /** exclusive */
  createdTo?: string;
  search?: string;
  userId?: number;
  /** the summary only */
  subscriptionId?: number;
  /** paid, but no subscription recorded for it yet */
  unfulfilled?: boolean;
  /** keyset cursor: orders listed after this one (the list only) */
  beforeId?: number;
  page?: number;
  pageSize?: number;
}

export function listTransactions(
  filters: TransactionListFilters = {},
  signal?: AbortSignal,
): Promise<TransactionListPage> {
  const params = new URLSearchParams();
  if (filters.status) params.set("status", filters.status);
  if (filters.gatewayType) params.set("gateway_type", filters.gatewayType);
  if (filters.purchaseType) params.set("purchase_type", filters.purchaseType);
  if (filters.createdFrom) params.set("created_from", filters.createdFrom);
  if (filters.createdTo) params.set("created_to", filters.createdTo);
  if (filters.search) params.set("search", filters.search);
  if (filters.userId !== undefined) params.set("user_id", String(filters.userId));
  if (filters.unfulfilled) params.set("unfulfilled", "true");
  if (filters.beforeId !== undefined) params.set("before_id", String(filters.beforeId));
  params.set("page", String(filters.page ?? 1));
  params.set("page_size", String(filters.pageSize ?? DEFAULT_PAGE_SIZE));

  return apiGet<TransactionListPage>(`/transactions?${params.toString()}`, signal);
}

/** "Load more" over a live list: continues after the last row on screen, so new orders don't repeat it. */
export async function listTransactionsAfter(
  filters: Omit<TransactionListFilters, "beforeId" | "page">,
  loaded: TransactionItem[] = [],
  signal?: AbortSignal,
): Promise<TransactionListPage> {
  const page = await listTransactions({ ...filters, beforeId: loaded.at(-1)?.id }, signal);
  return { items: page.items, total: loaded.length + page.total };
}

export interface TransactionSummary {
  report_currency: string;
  total_count: number;
  pending_count: number;
  paid_count: number;
  conversion_rate: string;
  revenue: string;
  average_check: string | null;
  average_discount: string | null;
  discount_amount: string;
  refunded_amount: string;
}

export function getTransactionSummary(
  filters: Omit<TransactionListFilters, "page" | "pageSize"> = {},
  signal?: AbortSignal,
): Promise<TransactionSummary> {
  const params = new URLSearchParams();
  if (filters.status) params.set("status", filters.status);
  if (filters.gatewayType) params.set("gateway_type", filters.gatewayType);
  if (filters.purchaseType) params.set("purchase_type", filters.purchaseType);
  if (filters.createdFrom) params.set("created_from", filters.createdFrom);
  if (filters.createdTo) params.set("created_to", filters.createdTo);
  if (filters.search) params.set("search", filters.search);
  if (filters.userId !== undefined) params.set("user_id", String(filters.userId));
  if (filters.subscriptionId !== undefined) params.set("subscription_id", String(filters.subscriptionId));
  if (filters.unfulfilled) params.set("unfulfilled", "true");
  return apiGet<TransactionSummary>(`/transactions/summary?${params.toString()}`, signal);
}

export function getTransaction(transactionId: number, signal?: AbortSignal): Promise<TransactionItem> {
  return apiGet<TransactionItem>(`/transactions/${transactionId}`, signal);
}

/** FAILED/CANCELED become PAID; a PAID order without a subscription is redispatched. */
export function fulfillTransaction(transactionId: number): Promise<TransactionItem> {
  return apiPost<TransactionItem, Record<string, never>>(`/transactions/${transactionId}/actions/fulfill`, {});
}

export interface RefundPreview {
  refundable: boolean;
  reason: string | null;
  rollback: { available: boolean; blocked_reason: string | null; old_term_expired: boolean } | null;
}

export interface RefundResult {
  transaction: TransactionItem;
  rollback_failed: boolean;
}

export function getRefundPreview(transactionId: number): Promise<RefundPreview> {
  return apiGet<RefundPreview>(`/transactions/${transactionId}/refund-preview`);
}

export function refundTransaction(transactionId: number, rollbackSubscription: boolean): Promise<RefundResult> {
  return apiPost<RefundResult, { rollback_subscription: boolean }>(
    `/transactions/${transactionId}/actions/refund`,
    { rollback_subscription: rollbackSubscription },
  );
}

export function canRefundTransaction(order: TransactionItem): boolean {
  return order.status === "PAID" && order.gateway_type === "TELEGRAM_STARS" && !order.is_test;
}

export function canFulfillTransaction(order: TransactionItem): boolean {
  if (order.status === "FAILED" || order.status === "CANCELED") return true;
  return order.status === "PAID" && order.fulfilled_subscription_id === null;
}

/** Gateway types that appear in at least one (non-test) order. */
export function listTransactionGateways(signal?: AbortSignal): Promise<string[]> {
  return apiGet<ListResponse<string>>("/transactions/gateways", signal).then((response) => response.items);
}

export interface UnratedAnchorCount {
  currency: string;
  count: number;
}

/** Migrated orders whose anchor amounts kept the nominal value: no rate at migration time. */
export function listUnratedAnchorAmounts(signal?: AbortSignal): Promise<UnratedAnchorCount[]> {
  return apiGet<ListResponse<UnratedAnchorCount>>("/transactions/unrated-anchor-amounts", signal).then(
    (response) => response.items,
  );
}

/** Converts them at the current rates; returns what is still left. */
export function rateUnratedAnchorAmounts(): Promise<UnratedAnchorCount[]> {
  return apiPost<ListResponse<UnratedAnchorCount>, Record<string, never>>(
    "/transactions/unrated-anchor-amounts/actions/rate",
    {},
  ).then((response) => response.items);
}

export const PURCHASE_TYPES: readonly PurchaseType[] = ["NEW", "RENEW", "CHANGE"];

/** The status filter's "paid, not issued" choice; sent as `unfulfilled`, not as a status. */
export const UNFULFILLED_STATUS = "UNFULFILLED";

export const CURRENCY_ICON: Record<string, LucideIcon> = { USD: DollarSign, XTR: Star, RUB: RussianRuble };

export const PAYMENT_STATUS_BADGE_TONE: Record<TransactionStatus, BadgeTone> = {
  PAID: "success",
  PENDING: "warning",
  FAILED: "error",
  CANCELED: "neutral",
  REFUNDED: "accent",
};

export const PAYMENT_STATUS_DOT_CLASSNAME: Record<TransactionStatus, string> = {
  PAID: "bg-success",
  PENDING: "bg-warning",
  FAILED: "bg-error",
  CANCELED: "bg-muted-foreground",
  REFUNDED: "bg-primary",
};
