import { apiGet, apiPost, apiPut } from "@shared/api/http";

// Decimal fields are serialized as strings by the backend (pydantic v2's
// JSON mode), not numbers -- keep them as strings end-to-end to avoid float
// precision loss on round-trip through <input type="number">.

export type Currency = "USD" | "XTR" | "RUB";
export type RoundingMode = "INTEGER" | "DECIMAL_2";
export type BulkAdjustScope = "ALL_PLANS" | "ALL_ADDONS";

export interface CurrencyRate {
  currency: Currency;
  rate: string;
  rounding_mode: RoundingMode;
  charm_ending: number | null;
  min_amount: string;
}

export interface PricingSettings {
  anchor_currency: Currency;
  price_per_day: string | null;
  price_per_gb: string | null;
}

export interface PriceBookCell {
  currency: Currency;
  amount: string;
  is_pinned: boolean;
}

export interface PriceBookRow {
  kind: "plan_duration" | "addon";
  ref_id: number;
  plan_id: number | null;
  label: string;
  days: number | null;
  base_price: string;
  cells: PriceBookCell[];
}

export interface PriceBook {
  rate_table: CurrencyRate[];
  settings: PricingSettings;
  plans: PriceBookRow[];
  addons: PriceBookRow[];
}

export interface PricingDiffRow {
  label: string;
  currency: Currency;
  old: string;
  new: string;
}

export interface PricingDiff {
  changes: PricingDiffRow[];
  affected_count: number;
}

export function getPriceBook(signal?: AbortSignal): Promise<PriceBook> {
  return apiGet<PriceBook>("/pricing/book", signal);
}

export interface UpdateCurrencyRateBody {
  rate: string;
  rounding_mode: RoundingMode;
  charm_ending: number | null;
  min_amount: string;
}

export function updateCurrencyRate(currency: Currency, body: UpdateCurrencyRateBody): Promise<PriceBook> {
  return apiPut<PriceBook, UpdateCurrencyRateBody>(`/pricing/rates/${currency}`, body);
}

export interface UpdatePricingSettingsBody {
  price_per_day: string | null;
  price_per_gb: string | null;
}

export function updatePricingSettings(body: UpdatePricingSettingsBody): Promise<PricingSettings> {
  return apiPut<PricingSettings, UpdatePricingSettingsBody>("/pricing/settings", body);
}

export function switchAnchorCurrency(newAnchor: Currency): Promise<PriceBook> {
  return apiPost<PriceBook, { new_anchor: Currency }>("/pricing/anchor", { new_anchor: newAnchor });
}

export interface AdjustBasePricesBody {
  scope: BulkAdjustScope;
  factor: string;
  plan_duration_ids: number[];
  addon_ids: number[];
}

export type PreviewPricingChangeBody =
  | { rate: UpdateCurrencyRateBody & { currency: Currency } }
  | { anchor: Currency }
  | { adjust: AdjustBasePricesBody };

export function previewPricingChange(body: PreviewPricingChangeBody): Promise<PricingDiff> {
  return apiPost<PricingDiff, PreviewPricingChangeBody>("/pricing/preview", body);
}

export function adjustBasePrices(body: AdjustBasePricesBody): Promise<PriceBook> {
  return apiPost<PriceBook, AdjustBasePricesBody>("/pricing/base/adjust", body);
}

export function setPlanDurationOverride(
  planId: number,
  days: number,
  currency: Currency,
  price: string | null,
): Promise<void> {
  return apiPut<unknown, { price: string | null }>(
    `/plans/${planId}/durations/${days}/override/${currency}`,
    { price },
  ).then(() => undefined);
}

export function setPlanDurationBasePrice(planId: number, days: number, basePrice: string): Promise<void> {
  return apiPut<unknown, { base_price: string }>(`/plans/${planId}/durations/${days}/base-price`, {
    base_price: basePrice,
  }).then(() => undefined);
}

export function setAddonOverride(addonId: number, currency: Currency, price: string | null): Promise<void> {
  return apiPut<unknown, { price: string | null }>(`/addons/${addonId}/override/${currency}`, {
    price,
  }).then(() => undefined);
}

export function setAddonBasePrice(addonId: number, basePrice: string): Promise<void> {
  return apiPut<unknown, { base_price: string }>(`/addons/${addonId}/base-price`, {
    base_price: basePrice,
  }).then(() => undefined);
}
