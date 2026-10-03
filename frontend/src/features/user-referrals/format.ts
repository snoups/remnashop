import type { TFunction } from "i18next";

import type { ReferralRewardType, ReferralUser } from "@entities/referrals/api";

export const REWARD_TYPES: ReferralRewardType[] = ["EXTRA_DAYS", "POINTS"];

export function formatReward(t: TFunction, type: ReferralRewardType, amount: string | number): string {
  const count = Math.trunc(Number(amount));
  return `${count} ${t(`referrals.units.${type}`, { count })}`;
}

/** one "+N unit" per reward type present */
export function formatRewardAmounts(t: TFunction, amounts: Partial<Record<ReferralRewardType, string>>): string[] {
  return REWARD_TYPES.flatMap((type) => {
    const amount = amounts[type];
    return amount === undefined ? [] : [`+${formatReward(t, type, amount)}`];
  });
}

export function userHandle(user: ReferralUser): string {
  if (user.username) return `@${user.username}`;
  if (user.email) return user.email;
  return user.telegram_id !== null ? `ID ${user.telegram_id}` : `#${user.id}`;
}
