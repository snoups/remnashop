import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { getPriceBook, type PriceBook } from "@entities/pricing/api";
import { CurrencyRatesPanel } from "@features/currency-rates-panel/CurrencyRatesPanel";
import { PricingMatrix } from "@features/pricing-matrix/PricingMatrix";

export function PricingPage() {
  const { t } = useTranslation();
  const [book, setBook] = useState<PriceBook | null>(null);
  const [hasError, setHasError] = useState(false);
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    let cancelled = false;
    getPriceBook()
      .then((result) => {
        if (!cancelled) setBook(result);
      })
      .catch(() => {
        if (!cancelled) setHasError(true);
      });
    return () => {
      cancelled = true;
    };
  }, [reloadToken]);

  const reload = () => setReloadToken((token) => token + 1);

  if (hasError) {
    return <p className="text-sm text-error">{t("pricing.loadError")}</p>;
  }

  if (!book) {
    return <p className="text-sm text-muted-foreground">{t("pricing.loading")}</p>;
  }

  return (
    <div className="flex flex-col gap-4">
      <CurrencyRatesPanel book={book} onChanged={reload} />
      <PricingMatrix book={book} onChanged={reload} />
    </div>
  );
}
