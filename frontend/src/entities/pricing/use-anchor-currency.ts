import { getPriceBook } from "@entities/pricing/api";
import { usePermissions } from "@entities/user/use-current-user";
import { useAsyncResource } from "@shared/lib/use-async-resource";

/** Plan base prices are in the anchor currency, which only the price book knows; null while unknown. */
export function useAnchorCurrency(): string | null {
  const canViewPricing = usePermissions().includes("PRICING_VIEW");
  const [state] = useAsyncResource(
    async (signal) => (canViewPricing ? (await getPriceBook(signal)).settings.anchor_currency : null),
    { deps: [canViewPricing], keepData: true },
  );
  return state.kind === "ready" ? state.data : null;
}
