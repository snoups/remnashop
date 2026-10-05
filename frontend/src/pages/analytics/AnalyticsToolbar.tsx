import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { Tag } from "@shared/ui/Tag";
import { PeriodPicker } from "@pages/analytics/PeriodPicker";

export function AnalyticsToolbar({
  currency,
  periodIndependent,
  tag,
}: {
  currency?: string;
  periodIndependent?: boolean;
  tag?: ReactNode;
}) {
  const { t } = useTranslation();

  let left: ReactNode = <span />;
  if (tag !== undefined) left = tag;
  else if (periodIndependent) {
    left = (
      <Tag>
        {t("analytics.periodIndependent")}
        {currency && (
          <>
            {" · "}
            <span className="text-foreground">{currency}</span>
          </>
        )}
      </Tag>
    );
  } else if (currency) {
    left = (
      <Tag>
        {t("analytics.reportCurrency")} · <span className="text-foreground">{currency}</span>
      </Tag>
    );
  }

  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      {left}
      {!periodIndependent && <PeriodPicker />}
    </div>
  );
}
