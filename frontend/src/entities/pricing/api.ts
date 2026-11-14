import type { TFunction } from "i18next";

import { apiGet, apiPost, apiPut } from "@shared/api/http";
import { formatDuration } from "@shared/lib/duration";

// Decimals arrive as strings (pydantic v2's JSON mode) and stay strings, so
// a round-trip through <input type="number"> loses no precision.

export type Currency = "USD" | "XTR" | "RUB";
export const CURRENCIES: readonly Currency[] = ["USD", "XTR", "RUB"];
export type RoundingMode = "INTEGER" | "DECIMAL_2";
export type BulkAdjustScope = "ALL_PLANS" | "ALL_ADDONS" | "SELECTED";

export interface CurrencyRate {
  currency: Currency;
  rate: string;
  rounding_mode: RoundingMode;
  charm_ending: number | null;
  min_amount: string;
}

export interface PricingSettings {
  anchor_currency: Currency;
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
  /** plain plan/add-on name; pair it with `days` via pricingRowLabel */
  name: string;
  days: number | null;
  base_price: string;
  cells: PriceBookCell[];
  /** a trial plan's duration at 0: free in every currency, nothing to price */
  is_free_trial: boolean;
}

export interface PriceBook {
  rate_table: CurrencyRate[];
  settings: PricingSettings;
  plans: PriceBookRow[];
  addons: PriceBookRow[];
}

export interface PricingDiffRow {
  name: string;
  days: number | null;
  currency: Currency;
  old: string;
  new: string;
}

export interface ScaledAmount {
  old: string;
  new: string;
}

export interface PricingDiff {
  changes: PricingDiffRow[];
  affected_count: number;
  // filled only for an anchor switch
  loyalty_thresholds: ScaledAmount[];
  rescaled_transactions: number;
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

export function switchAnchorCurrency(newAnchor: Currency): Promise<PriceBook> {
  return apiPost<PriceBook, { new_anchor: Currency }>("/pricing/actions/switch-anchor", { new_anchor: newAnchor });
}

export type PriceAdjustMode = "MULTIPLY" | "SET" | "LADDER";
export type PinnedPriceAction = "KEEP" | "SCALE" | "RESET";

export interface AdjustBasePricesBody {
  scope: BulkAdjustScope;
  mode: PriceAdjustMode;
  /** MULTIPLY */
  factor?: string;
  /** SET: the new price; LADDER: the base duration's price */
  price?: string;
  /** LADDER: the duration `price` is for */
  ladder_base_days?: number;
  /** LADDER: percent off by duration in days; negative is a markup */
  ladder_discounts?: Record<number, string>;
  pinned: PinnedPriceAction;
  plan_duration_ids: number[];
  addon_ids: number[];
}

export type PreviewPricingChangeBody =
  | { rate: UpdateCurrencyRateBody & { currency: Currency } }
  | { anchor: Currency }
  | { adjust: AdjustBasePricesBody };

export function previewPricingChange(body: PreviewPricingChangeBody): Promise<PricingDiff> {
  return apiPost<PricingDiff, PreviewPricingChangeBody>("/pricing/actions/preview", body);
}

export function adjustBasePrices(body: AdjustBasePricesBody): Promise<PriceBook> {
  return apiPost<PriceBook, AdjustBasePricesBody>("/pricing/actions/adjust-base-prices", body);
}

export interface SetMatrixPricesBody {
  plan_base_prices: { plan_id: number; days: number; base_price: string }[];
  plan_overrides: { plan_id: number; days: number; currency: Currency; price: string | null }[];
  addon_base_prices: { addon_id: number; base_price: string }[];
  addon_overrides: { addon_id: number; currency: Currency; price: string | null }[];
}

/** Every edit of the matrix in one transaction: all of them land, or none. */
export function setMatrixPrices(body: SetMatrixPricesBody): Promise<PriceBook> {
  return apiPost<PriceBook, SetMatrixPricesBody>("/pricing/bulk/set-prices", body);
}

/** "Стандарт · 30 дн." for a plan duration, just the name for an add-on. */
export function pricingRowLabel(
  row: { name: string; days: number | null },
  t: TFunction,
): string {
  return row.days === null ? row.name : `${row.name} · ${formatDuration(row.days, t)}`;
}
