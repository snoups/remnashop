import { useTranslation } from "react-i18next";

import { type PricingDiff, pricingRowLabel } from "@entities/pricing/api";
import { EYEBROW_CLASS } from "@shared/ui/classes";

// "+10%" / "−15%"; nothing when the old price was zero
function percentChange(oldValue: string, newValue: string): string {
  const before = Number(oldValue);
  if (before === 0) return "";
  const percent = ((Number(newValue) - before) / before) * 100;
  const rounded = Math.round(percent * 10) / 10;
  return `${rounded > 0 ? "+" : rounded < 0 ? "−" : ""}${Math.abs(rounded)}%`;
}

interface PricingDiffListProps {
  diff: PricingDiff;
}

export function PricingDiffList({ diff }: PricingDiffListProps) {
  const { t } = useTranslation();

  const extras: { label: string; old: string; new: string }[] = [
    ...(diff.price_per_day ? [{ label: t("pricing.settings.pricePerDayLabel"), ...diff.price_per_day }] : []),
    ...(diff.price_per_gb ? [{ label: t("pricing.settings.pricePerGbLabel"), ...diff.price_per_gb }] : []),
    ...diff.loyalty_thresholds.map((threshold) => ({ label: t("pricing.diff.loyaltyThreshold"), ...threshold })),
  ];

  if (diff.changes.length === 0 && extras.length === 0) {
    return <p className="text-xs text-muted-foreground">{t("pricing.diff.empty")}</p>;
  }

  return (
    <div className="space-y-2">
      {/* clipping on the outer box keeps the scrollbar inside the rounded corners */}
      <div className="-mx-1 glass-well overflow-hidden rounded-xl">
        <div className="relative max-h-56 overflow-auto">
          <table className="w-full border-separate border-spacing-0 text-xs">
            <thead>
              <tr className={`text-left ${EYEBROW_CLASS}`}>
                <th scope="col" className="border-b border-border px-3 py-2 font-semibold">{t("pricing.matrix.item")}</th>
                <th scope="col" className="border-b border-border px-3 py-2 font-semibold">{t("pricing.diff.old")}</th>
                <th scope="col" className="border-b border-border px-3 py-2 font-semibold">{t("pricing.diff.new")}</th>
                <th scope="col" className="border-b border-border px-3 py-2 text-right font-semibold">{t("pricing.diff.change")}</th>
              </tr>
            </thead>
            <tbody className="[&>tr:not(:last-child)>td]:border-b [&>tr:not(:last-child)>td]:border-border/50">
              {diff.changes.map((change, index) => (
                <tr key={`${change.name}-${change.days}-${change.currency}-${index}`}>
                  <td className="px-3 py-1.5 text-foreground/90">
                    {pricingRowLabel(change, t)} <span className="text-muted-foreground">{change.currency}</span>
                  </td>
                  <td className="px-3 py-1.5 text-muted-foreground">{change.old}</td>
                  <td className="px-3 py-1.5 font-medium text-foreground">{change.new}</td>
                  <td className="px-3 py-1.5 text-right tabular-nums text-muted-foreground">{percentChange(change.old, change.new)}</td>
                </tr>
              ))}
              {extras.map((extra, index) => (
                <tr key={`extra-${index}`}>
                  <td className="px-3 py-1.5 text-foreground/90">{extra.label}</td>
                  <td className="px-3 py-1.5 text-muted-foreground">{extra.old}</td>
                  <td className="px-3 py-1.5 font-medium text-foreground">{extra.new}</td>
                  <td className="px-3 py-1.5 text-right tabular-nums text-muted-foreground">{percentChange(extra.old, extra.new)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      {diff.rescaled_transactions > 0 && (
        <p className="text-xs text-muted-foreground">
          {t("pricing.diff.rescaledTransactions", { count: diff.rescaled_transactions })}
        </p>
      )}
    </div>
  );
}
