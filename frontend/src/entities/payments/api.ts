import { apiGet } from "@shared/api/http";

export type PaymentOrderStatus = "PENDING" | "PAID" | "FAILED" | "EXPIRED" | "CANCELED";
export type PurchaseType = "NEW" | "RENEW" | "CHANGE";
export type DiscountSource = "NONE" | "PERSONAL" | "PURCHASE";

export interface PlanSnapshot {
  name?: string;
  public_code?: string;
}

export interface PaymentOrderItem {
  id: number;
  user_id: number;
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
}

export const DEFAULT_PAGE_SIZE = 50;

export interface PaymentOrderListPage {
  items: PaymentOrderItem[];
  total: number;
}

export interface PaymentOrderListFilters {
  status?: PaymentOrderStatus;
  page?: number;
  pageSize?: number;
}

export function listPaymentOrders(
  filters: PaymentOrderListFilters = {},
  signal?: AbortSignal,
): Promise<PaymentOrderListPage> {
  const params = new URLSearchParams();
  if (filters.status) params.set("status", filters.status);
  params.set("page", String(filters.page ?? 1));
  params.set("page_size", String(filters.pageSize ?? DEFAULT_PAGE_SIZE));

  return apiGet<PaymentOrderListPage>(`/payments/orders?${params.toString()}`, signal);
}

// Mirrors backend/app/core/enums.py's Currency.symbol.
export const CURRENCY_SYMBOL: Record<string, string> = { USD: "$", XTR: "★", RUB: "₽" };
