import { getPriceBook } from "@entities/pricing/api";
import { OldPricingMatrix } from "@pages/debug/old-pricing/OldPricingMatrix";
import { useAsyncResource } from "@shared/lib/use-async-resource";

export function OldPricingPreview() {
  const [state] = useAsyncResource(getPriceBook);
  return state.kind === "ready" ? <OldPricingMatrix book={state.data} /> : null;
}
