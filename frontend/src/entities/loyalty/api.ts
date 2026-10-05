import { apiGet, apiPatch, apiPut } from "@shared/api/http";

export interface LoyaltyTier {
  threshold: string;
  percent: number;
}

export interface LoyaltySettings {
  enabled: boolean;
  window_months: number | null;
  tiers: LoyaltyTier[];
  currency: string | null;
}

export type SaveLoyaltySettingsRequest = Omit<LoyaltySettings, "currency">;

export interface UserLoyalty {
  discount: number;
  excluded: boolean;
  spent: string;
  next_tier: LoyaltyTier | null;
  currency: string;
}

export function getLoyaltySettings(signal?: AbortSignal): Promise<LoyaltySettings> {
  return apiGet<LoyaltySettings>("/loyalty/settings", signal);
}

export function saveLoyaltySettings(payload: SaveLoyaltySettingsRequest): Promise<LoyaltySettings> {
  return apiPut<LoyaltySettings, SaveLoyaltySettingsRequest>("/loyalty/settings", payload);
}

export function getUserLoyalty(userId: number, signal?: AbortSignal): Promise<UserLoyalty> {
  return apiGet<UserLoyalty>(`/users/${userId}/loyalty`, signal);
}

export function setUserLoyaltyExcluded(userId: number, excluded: boolean): Promise<UserLoyalty> {
  return apiPatch<UserLoyalty, { excluded: boolean }>(`/users/${userId}/loyalty`, { excluded });
}
