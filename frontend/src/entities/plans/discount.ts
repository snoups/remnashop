import type { Plan } from "@entities/plans/api";
import type { BadgeTone } from "@shared/ui/Badge";

export type PlanDiscountStatus = "scheduled" | "active" | "ended";

export function planDiscountStatus(plan: Plan, now = Date.now()): PlanDiscountStatus | null {
  if (plan.discount_percent <= 0) return null;
  if (plan.discount_starts_at && now < new Date(plan.discount_starts_at).getTime()) return "scheduled";
  if (plan.discount_ends_at && now >= new Date(plan.discount_ends_at).getTime()) return "ended";
  return "active";
}

export const PLAN_DISCOUNT_STATUS_TONE: Record<PlanDiscountStatus, BadgeTone> = {
  scheduled: "violet",
  active: "success",
  ended: "neutral",
};
