import { useTranslation } from "react-i18next";

import { getPriceBook } from "@entities/pricing/api";
import { CurrencyRatesPanel } from "@features/currency-rates-panel/CurrencyRatesPanel";
import { PricingMatrix } from "@features/pricing-matrix/PricingMatrix";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { Spinner } from "@shared/ui/Spinner";

export function PricingPage() {
  const { t } = useTranslation();
  const [state, reload] = useAsyncResource(getPriceBook);

  if (state.kind === "error") {
    return <p className="text-sm text-error">{t("pricing.loadError")}</p>;
  }

  if (state.kind === "loading") {
    return <Spinner />;
  }

  return (
    <div className="flex flex-col gap-4">
      <CurrencyRatesPanel book={state.data} onChanged={reload} />
      <PricingMatrix book={state.data} onChanged={reload} />
    </div>
  );
}
