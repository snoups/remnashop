import { apiGet } from "@shared/api/http";

export type PaymentOrderStatus = "PENDING" | "PAID" | "FAILED" | "CANCELED" | "REFUNDED";
export type PurchaseType = "NEW" | "RENEW" | "CHANGE";
export type DiscountSource = "NONE" | "PERSONAL" | "PURCHASE";

export interface PlanSnapshot {
  name?: string;
  public_code?: string;
}

export interface PaymentOrderUser {
  name: string;
  username: string | null;
  telegram_id: number | null;
  email: string | null;
}

export interface PaymentOrderItem {
  id: number;
  user_id: number;
  /** null once the user is deleted */
  user: PaymentOrderUser | null;
  plan_id: number | null;
  plan_snapshot: PlanSnapshot;
  duration_days: number;
  currency: string;
  purchase_type: PurchaseType;
  target_subscription_id: number | null;
  gateway_type: string;
  external_payment_id: string | null;
  status: PaymentOrderStatus;
  base_price: string;
  discount_percent: number;
  discount_source: DiscountSource;
  final_price: string;
  customer_email: string | null;
  idempotency_key: string;
  expires_at: string;
  created_at: string;
}

export const DEFAULT_PAGE_SIZE = 50;

export interface PaymentOrderListPage {
  items: PaymentOrderItem[];
  total: number;
}

export interface PaymentOrderListFilters {
  status?: PaymentOrderStatus;
  gatewayType?: string;
  purchaseType?: PurchaseType;
  createdFrom?: string;
  search?: string;
  page?: number;
  pageSize?: number;
}

export function listPaymentOrders(
  filters: PaymentOrderListFilters = {},
  signal?: AbortSignal,
): Promise<PaymentOrderListPage> {
  const params = new URLSearchParams();
  if (filters.status) params.set("status", filters.status);
  if (filters.gatewayType) params.set("gateway_type", filters.gatewayType);
  if (filters.purchaseType) params.set("purchase_type", filters.purchaseType);
  if (filters.createdFrom) params.set("created_from", filters.createdFrom);
  if (filters.search) params.set("search", filters.search);
  params.set("page", String(filters.page ?? 1));
  params.set("page_size", String(filters.pageSize ?? DEFAULT_PAGE_SIZE));

  return apiGet<PaymentOrderListPage>(`/payments/orders?${params.toString()}`, signal);
}

/** Gateway types that appear in at least one (non-test) order. */
export function listPaymentOrderGateways(signal?: AbortSignal): Promise<string[]> {
  return apiGet<string[]>("/payments/orders/gateways", signal);
}

export const PURCHASE_TYPES: readonly PurchaseType[] = ["NEW", "RENEW", "CHANGE"];

// Mirrors backend/app/core/enums.py's Currency.symbol.
export const CURRENCY_SYMBOL: Record<string, string> = { USD: "$", XTR: "★", RUB: "₽" };

export const PAYMENT_STATUS_BADGE_CLASSNAME: Record<PaymentOrderStatus, string> = {
  PAID: "border-success/30 bg-success/10 text-success",
  PENDING: "border-warning/30 bg-warning/10 text-warning",
  FAILED: "border-error/30 bg-error/10 text-error",
  CANCELED: "border-border bg-white/[0.04] text-muted-foreground",
  REFUNDED: "border-primary/30 bg-primary/10 text-primary",
};
