import { Coins } from "lucide-react";
import { useTranslation } from "react-i18next";

import { getPriceBook } from "@entities/pricing/api";
import { CurrencyRatesPanel } from "@features/currency-rates-panel/CurrencyRatesPanel";
import { PricingMatrix } from "@features/pricing-matrix/PricingMatrix";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { ErrorState } from "@shared/ui/glass/EmptyState";
import { Section } from "@shared/ui/glass/Section";
import { Spinner } from "@shared/ui/Spinner";

export function PricingPage() {
  const { t } = useTranslation();
  const [state, reload, setBook] = useAsyncResource(getPriceBook);

  if (state.kind === "error") {
    return (
      <Section icon={Coins} title={t("pricing.rates.title")} description={t("pricing.rates.description")}>
        <ErrorState text={t("common.loadError")} />
      </Section>
    );
  }

  if (state.kind === "loading") {
    return <Spinner size="page" />;
  }

  return (
    <div className="flex min-w-0 flex-col gap-5">
      <CurrencyRatesPanel book={state.data} onChanged={reload} />
      <PricingMatrix book={state.data} onChanged={reload} onSaved={setBook} />
    </div>
  );
}
