import { useTranslation } from "react-i18next";

import { type PricingDiff, pricingRowLabel } from "@entities/pricing/api";
import { Card } from "@shared/ui/Card";
import { EYEBROW_CLASS } from "@shared/ui/classes";

interface PricingDiffListProps {
  diff: PricingDiff;
}

export function PricingDiffList({ diff }: PricingDiffListProps) {
  const { t } = useTranslation();

  if (diff.changes.length === 0) {
    return <p className="text-[12.5px] text-muted-foreground">{t("pricing.diff.empty")}</p>;
  }

  return (
    // clipping on the outer box keeps the scrollbar inside the rounded corners
    <Card variant="bare" className="overflow-hidden">
      <div className="max-h-56 overflow-y-auto">
        <table className="w-full border-separate border-spacing-0 text-[12px]">
          <thead>
            <tr className={`text-left ${EYEBROW_CLASS}`}>
              <th className="border-b border-border px-2.5 pb-1.5 pt-2 font-semibold">{t("pricing.matrix.item")}</th>
              <th className="border-b border-border px-2.5 pb-1.5 pt-2 font-semibold">{t("pricing.diff.old")}</th>
              <th className="border-b border-border px-2.5 pb-1.5 pt-2 font-semibold">{t("pricing.diff.new")}</th>
            </tr>
          </thead>
          <tbody className="[&>tr:not(:last-child)>td]:border-b [&>tr:not(:last-child)>td]:border-border/50">
            {diff.changes.map((change, index) => (
              <tr key={`${change.name}-${change.days}-${change.currency}-${index}`}>
                <td className="px-2.5 py-1.5 text-foreground/90">
                  {pricingRowLabel(change, t)} <span className="text-muted-foreground">{change.currency}</span>
                </td>
                <td className="px-2.5 py-1.5 text-muted-foreground">{change.old}</td>
                <td className="px-2.5 py-1.5 font-medium text-foreground">{change.new}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
