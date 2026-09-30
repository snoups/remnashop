import { CURRENCY_SYMBOL } from "@entities/payments/api";

/** `exact` keeps kopecks/cents when there are any (a single order), otherwise whole units (totals). */
export function formatMoney(amount: string, currency: string, language: string, exact = false): string {
  const digits = exact && Number(amount) % 1 !== 0 ? 2 : 0;
  const value = new Intl.NumberFormat(language, { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(
    Number(amount),
  );
  const symbol = CURRENCY_SYMBOL[currency];
  return symbol ? `${value} ${symbol}` : `${value} ${currency}`;
}

// Backend sends conversion/ROI as fractions (0.5 = 50%).
export function formatPercent(fraction: string, language: string, signed = false): string {
  return new Intl.NumberFormat(language, {
    style: "percent",
    maximumFractionDigits: 1,
    signDisplay: signed ? "exceptZero" : "auto",
  }).format(Number(fraction));
}

export function roiClassName(roi: string | null): string {
  if (roi === null) return "text-muted-foreground";
  return Number(roi) >= 0 ? "text-success" : "text-error";
}
