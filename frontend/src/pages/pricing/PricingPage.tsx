import { Coins } from "lucide-react";
import { useTranslation } from "react-i18next";

import { getPriceBook } from "@entities/pricing/api";
import { CurrencyRatesPanel } from "@features/currency-rates-panel/CurrencyRatesPanel";
import { PricingMatrix } from "@features/pricing-matrix/PricingMatrix";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { Card } from "@shared/ui/Card";
import { CardHeader } from "@shared/ui/CardHeader";
import { ErrorState } from "@shared/ui/EmptyState";
import { Spinner } from "@shared/ui/Spinner";

export function PricingPage() {
  const { t } = useTranslation();
  const [state, reload] = useAsyncResource(getPriceBook);

  if (state.kind === "error") {
    return (
      <Card>
        <CardHeader icon={Coins} title={t("pricing.rates.title")} description={t("pricing.rates.description")} />
        <ErrorState text={t("common.loadError")} />
      </Card>
    );
  }

  if (state.kind === "loading") {
    return <Spinner size="page" />;
  }

  return (
    <div className="flex flex-col gap-4">
      <CurrencyRatesPanel book={state.data} onChanged={reload} />
      <PricingMatrix book={state.data} onChanged={reload} />
    </div>
  );
}
