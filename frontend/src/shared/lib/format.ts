// Mirrors backend/app/core/enums.py's Currency.symbol.
const CURRENCY_SYMBOL: Readonly<Record<string, string>> = { USD: "$", XTR: "★", RUB: "₽" };

export function currencySymbol(currency: string): string {
  return CURRENCY_SYMBOL[currency] ?? currency;
}

/**
 * The locale's own currency format: "1 234 ₽" in ru, "₽1,234" in en. `exact`
 * keeps kopecks/cents when there are any (a single order, an average), otherwise
 * whole units (totals). Telegram Stars aren't an ISO currency, so Intl can't
 * format them: always "1 234 ★".
 */
export function formatMoney(amount: string | number, currency: string, language: string, exact = false): string {
  const value = Number(amount);
  const digits = exact && value % 1 !== 0 ? 2 : 0;
  const number = { minimumFractionDigits: digits, maximumFractionDigits: digits };
  if (currency === "XTR") return `${new Intl.NumberFormat(language, number).format(value)} ★`;
  try {
    return new Intl.NumberFormat(language, {
      ...number,
      style: "currency",
      currency,
      currencyDisplay: "narrowSymbol",
    }).format(value);
  } catch {
    // no currency yet (a summary still loading) or a malformed code
    return new Intl.NumberFormat(language, number).format(value);
  }
}

/** A fraction as a percent (0.5 -> "50 %" in ru, "50%" in en); the backend sends rates as fractions. */
export function formatPercent(fraction: string | number, language: string, signed = false): string {
  return new Intl.NumberFormat(language, {
    style: "percent",
    maximumFractionDigits: 1,
    signDisplay: signed ? "exceptZero" : "auto",
  }).format(Number(fraction));
}

const BYTE_UNITS = ["byte", "kilobyte", "megabyte", "gigabyte", "terabyte"] as const;

/** "1,5 ГБ" / "1.5 GB": binary steps, unit names from Intl. */
export function formatBytes(bytes: number, language: string): string {
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < BYTE_UNITS.length - 1) {
    value /= 1024;
    unit++;
  }
  return new Intl.NumberFormat(language, {
    style: "unit",
    unit: BYTE_UNITS[unit],
    unitDisplay: "short",
    maximumFractionDigits: unit === 0 ? 0 : 1,
  }).format(value);
}
