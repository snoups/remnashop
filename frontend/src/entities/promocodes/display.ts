import { ArrowDownUp, BadgePercent, CalendarPlus, Crown, Percent, Smartphone } from "lucide-react";
import type { ComponentType } from "react";

import type { AddOnListItem } from "@entities/addons/api";
import type { Plan } from "@entities/plans/api";
import type {
  Promocode,
  PromocodeAvailability,
  PromocodeRewardType,
  UpdatePromocodeRequest,
} from "@entities/promocodes/api";
import { parseOptionalInt } from "@shared/lib/number-input";

export type PromocodeStatus = "ACTIVE" | "INACTIVE" | "EXPIRED";
export type PromocodeReward = Pick<
  Promocode,
  "reward_type" | "reward" | "reward_addon_id" | "reward_plan_id" | "reward_duration_days"
>;
export interface PromocodeLimitsDraft {
  availability: PromocodeAvailability;
  allowedUserIds: number[];
  expiresAt: string;
  maxActivations: string;
  isReusable: boolean;
}
type LimitsPayload = Required<Omit<UpdatePromocodeRequest, "is_active">>;
type TranslateFn = (key: string) => string;

export const PROMOCODE_STATUSES: PromocodeStatus[] = ["ACTIVE", "INACTIVE", "EXPIRED"];
export const REWARD_TYPES: PromocodeRewardType[] = [
  "DURATION",
  "TRAFFIC",
  "DEVICES",
  "SUBSCRIPTION",
  "PERSONAL_DISCOUNT",
  "PURCHASE_DISCOUNT",
];
export const AVAILABILITIES: PromocodeAvailability[] = ["ALL", "NEW", "EXISTING", "INVITED", "ALLOWED"];

export const REWARD_TYPE_ICON: Record<PromocodeRewardType, ComponentType<{ className?: string }>> = {
  DURATION: CalendarPlus,
  TRAFFIC: ArrowDownUp,
  DEVICES: Smartphone,
  SUBSCRIPTION: Crown,
  PERSONAL_DISCOUNT: BadgePercent,
  PURCHASE_DISCOUNT: Percent,
};

export const PROMOCODE_STATUS_BADGE_CLASSNAME: Record<PromocodeStatus, string> = {
  ACTIVE: "border-success/30 bg-success/10 text-success",
  INACTIVE: "border-border bg-white/[0.04] text-muted-foreground",
  EXPIRED: "border-warning/30 bg-warning/10 text-warning",
};

export function getPromocodeStatus(promo: Promocode): PromocodeStatus {
  if (promo.expires_at && new Date(promo.expires_at).getTime() < Date.now()) return "EXPIRED";
  return promo.is_active ? "ACTIVE" : "INACTIVE";
}

export function describeReward(
  promo: PromocodeReward,
  addons: AddOnListItem[],
  plans: Plan[],
  t: TranslateFn,
): string {
  switch (promo.reward_type) {
    case "DURATION":
      return `+${promo.reward ?? 0}d`;
    case "TRAFFIC":
    case "DEVICES": {
      const addon = addons.find((a) => a.id === promo.reward_addon_id);
      return addon ? `+${addon.name}` : t(`promocodes.rewardType.${promo.reward_type}`);
    }
    case "SUBSCRIPTION": {
      const plan = plans.find((p) => p.id === promo.reward_plan_id);
      const planLabel = plan ? plan.name : t("promocodes.rewardType.SUBSCRIPTION");
      return `${planLabel} · ${promo.reward_duration_days ?? 0}d`;
    }
    case "PERSONAL_DISCOUNT":
    case "PURCHASE_DISCOUNT":
      return `-${promo.reward ?? 0}%`;
    default:
      return t(`promocodes.rewardType.${promo.reward_type}`);
  }
}

export function limitsDraftOf(promo: Promocode): PromocodeLimitsDraft {
  return {
    availability: promo.availability,
    allowedUserIds: promo.allowed_user_ids,
    expiresAt: promo.expires_at ? promo.expires_at.slice(0, 10) : "",
    maxActivations: promo.max_activations !== null ? String(promo.max_activations) : "",
    isReusable: promo.is_reusable,
  };
}

/** undefined means the activation limit isn't a valid number -- reject the submit. */
export function limitsToPayload(draft: PromocodeLimitsDraft): LimitsPayload | undefined {
  const maxActivations = parseOptionalInt(draft.maxActivations, 1);
  if (maxActivations === undefined) return undefined;
  return {
    availability: draft.availability,
    // the hidden allowlist is dropped with it, not left dangling on the row
    allowed_user_ids: draft.availability === "ALLOWED" ? draft.allowedUserIds : [],
    expires_at: draft.expiresAt ? `${draft.expiresAt}T23:59:59.000Z` : null,
    max_activations: maxActivations,
    is_reusable: draft.isReusable,
  };
}
