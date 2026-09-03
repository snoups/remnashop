import { useTranslation } from "react-i18next";

import type { PricingDiff } from "@entities/pricing/api";

interface PricingDiffListProps {
  diff: PricingDiff;
}

export function PricingDiffList({ diff }: PricingDiffListProps) {
  const { t } = useTranslation();

  if (diff.changes.length === 0) {
    return <p className="text-[12.5px] text-muted-foreground">{t("pricing.diff.empty")}</p>;
  }

  return (
    <div className="max-h-56 overflow-y-auto rounded-xl border border-border">
      <table className="w-full text-[12px]">
        <thead>
          <tr className="text-left text-muted-foreground">
            <th className="px-2.5 py-1.5 font-medium">{t("pricing.matrix.item")}</th>
            <th className="px-2.5 py-1.5 font-medium">{t("pricing.diff.old")}</th>
            <th className="px-2.5 py-1.5 font-medium">{t("pricing.diff.new")}</th>
          </tr>
        </thead>
        <tbody>
          {diff.changes.map((change, index) => (
            <tr key={`${change.label}-${change.currency}-${index}`} className="border-t border-border">
              <td className="px-2.5 py-1.5 text-foreground/90">
                {change.label} <span className="text-muted-foreground">{change.currency}</span>
              </td>
              <td className="px-2.5 py-1.5 text-muted-foreground">{change.old}</td>
              <td className="px-2.5 py-1.5 font-medium text-foreground">{change.new}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
