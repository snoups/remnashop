import { previewAudience } from "@entities/broadcasts/api";
import type { AudiencePreview, BroadcastAudience, BroadcastCategory, BroadcastDelivery } from "@entities/broadcasts/api";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import type { AsyncState } from "@shared/lib/use-async-resource";
import { useDebouncedValue } from "@shared/lib/use-debounced-value";

const PREVIEW_DEBOUNCE_MS = 400;
const EMPTY_PREVIEW: AudiencePreview = { total: 0, by_locale: {}, by_channel: {} };

interface AudiencePreviewResult {
  /** zero while the audience can't be counted yet (no customers picked, half a date range) */
  state: AsyncState<AudiencePreview>;
  /** the total for exactly the current audience, or null while unknown or out of date */
  freshTotal: number | null;
}

export function useAudiencePreview(
  audience: BroadcastAudience,
  category: BroadcastCategory,
  delivery: BroadcastDelivery,
  emailFallback: boolean,
  enabled: boolean,
): AudiencePreviewResult {
  const current = JSON.stringify({ audience, category, delivery, emailFallback, enabled });
  const key = useDebouncedValue(current, PREVIEW_DEBOUNCE_MS);
  const [raw] = useAsyncResource(
    async (signal) => {
      const parsed = JSON.parse(key) as {
        audience: BroadcastAudience;
        category: BroadcastCategory;
        delivery: BroadcastDelivery;
        emailFallback: boolean;
        enabled: boolean;
      };
      const data = parsed.enabled
        ? await previewAudience(parsed.audience, parsed.category, parsed.delivery, parsed.emailFallback, signal)
        : EMPTY_PREVIEW;
      return { key, data };
    },
    { deps: [key], keepData: true },
  );
  if (raw.kind !== "ready") return { state: raw, freshTotal: null };
  return {
    state: { kind: "ready", data: raw.data.data },
    freshTotal: enabled && raw.data.key === current ? raw.data.data.total : null,
  };
}
