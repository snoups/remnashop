import type { ParseKeys, TFunction } from "i18next";
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
import { formatDuration } from "@shared/lib/duration";
import { endOfDayToIso, isoToLastDay } from "@shared/lib/iso-date";
import { parseOptionalInt } from "@shared/lib/number-input";
import type { BadgeTone } from "@shared/ui/Badge";

export type PromocodeStatus = "ACTIVE" | "INACTIVE" | "EXPIRED" | "EXHAUSTED";
export type PromocodeReward = Pick<
  Promocode,
  "reward_type" | "reward" | "reward_addon_id" | "reward_plan_id" | "reward_duration_days"
>;
export interface PromocodeLimitsDraft {
  availability: PromocodeAvailability;
  allowedUserIds: number[];
  allowedPlanIds: number[];
  expiresAt: string;
  maxActivations: string;
  isReusable: boolean;
}
type LimitsPayload = Required<Omit<UpdatePromocodeRequest, "is_active">>;

export const PROMOCODE_STATUSES: PromocodeStatus[] = ["ACTIVE", "EXHAUSTED", "INACTIVE", "EXPIRED"];
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

export const PROMOCODE_STATUS_BADGE_TONE: Record<PromocodeStatus, BadgeTone> = {
  ACTIVE: "success",
  INACTIVE: "neutral",
  EXPIRED: "warning",
  EXHAUSTED: "warning",
};

export function getPromocodeStatus(promo: Promocode): PromocodeStatus {
  if (promo.expires_at && new Date(promo.expires_at).getTime() < Date.now()) return "EXPIRED";
  if (!promo.is_active) return "INACTIVE";
  // mirrors the backend's status filter
  if (promo.max_activations !== null && promo.activations_count >= promo.max_activations) return "EXHAUSTED";
  return "ACTIVE";
}

export function describeReward(
  promo: PromocodeReward,
  addons: AddOnListItem[],
  plans: Plan[],
  t: TFunction,
): string {
  switch (promo.reward_type) {
    case "DURATION":
      return `+${t("plans.daysShort", { count: promo.reward ?? 0 })}`;
    case "TRAFFIC":
    case "DEVICES": {
      const addon = addons.find((a) => a.id === promo.reward_addon_id);
      return addon ? `+${addon.name}` : t(`promocodes.rewardType.${promo.reward_type}`);
    }
    case "SUBSCRIPTION": {
      const plan = plans.find((p) => p.id === promo.reward_plan_id);
      const planLabel = plan ? plan.name : t("promocodes.rewardType.SUBSCRIPTION");
      return `${planLabel} · ${formatDuration(promo.reward_duration_days ?? 0, t)}`;
    }
    case "PERSONAL_DISCOUNT":
    case "PURCHASE_DISCOUNT":
      return `-${promo.reward ?? 0}%`;
    default:
      return t(`promocodes.rewardType.${promo.reward_type}` as ParseKeys);
  }
}

export function limitsDraftOf(promo: Promocode): PromocodeLimitsDraft {
  return {
    availability: promo.availability,
    allowedUserIds: promo.allowed_user_ids,
    allowedPlanIds: promo.allowed_plan_ids,
    expiresAt: isoToLastDay(promo.expires_at),
    maxActivations: promo.max_activations !== null ? String(promo.max_activations) : "",
    isReusable: promo.is_reusable,
  };
}

/** rewards applied to a chosen subscription, the only ones a plan list limits */
export const PLAN_LIMITED_REWARDS: PromocodeRewardType[] = ["DURATION", "TRAFFIC", "DEVICES"];

/** undefined means the activation limit isn't a valid number; reject the submit. */
export function limitsToPayload(
  draft: PromocodeLimitsDraft,
  rewardType: PromocodeRewardType,
): LimitsPayload | undefined {
  const maxActivations = parseOptionalInt(draft.maxActivations, 1);
  if (maxActivations === undefined) return undefined;
  return {
    availability: draft.availability,
    // the hidden allowlist is dropped with it, not left dangling on the row
    allowed_user_ids: draft.availability === "ALLOWED" ? draft.allowedUserIds : [],
    allowed_plan_ids: PLAN_LIMITED_REWARDS.includes(rewardType) ? draft.allowedPlanIds : [],
    // the end of the picked day in the admin's own time zone, as the list shows it
    expires_at: endOfDayToIso(draft.expiresAt),
    max_activations: maxActivations,
    is_reusable: draft.isReusable,
  };
}
