import type { PurchaseType } from "@entities/payments/api";

export const PURCHASE_TYPE_BAR_CLASS: Record<PurchaseType, string> = {
  NEW: "bg-primary",
  RENEW: "bg-primary/45",
  CHANGE: "bg-foreground/50",
};
