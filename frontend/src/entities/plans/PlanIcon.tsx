import { Icon } from "lucide-react";
import { useState, type ReactNode } from "react";

import { emojiThumbnailUrl } from "@entities/emoji-packs/api";
import { LUCIDE_PACK_ICONS } from "@entities/emoji-packs/lucide-pack";
import type { PlanIconValue } from "@entities/plans/api";

// the static thumbnail: PremiumEmoji's animation would bring lottie into every page showing a plan
function EmojiByThumbnail({ id, glyph, size }: { id: string; glyph: string; size: number }) {
  const [failed, setFailed] = useState(false);
  if (failed) return <span style={{ fontSize: size }}>{glyph}</span>;
  return (
    <img
      src={emojiThumbnailUrl(id)}
      alt={glyph}
      draggable={false}
      onError={() => setFailed(true)}
      width={size}
      height={size}
      className="shrink-0 object-contain"
    />
  );
}

/** The emoji an admin picked for a plan, or `fallback` when there is none. */
export function PlanIcon({ icon, size, fallback }: { icon: PlanIconValue; size: number; fallback: ReactNode }) {
  if (!icon.icon_emoji_id) return fallback;
  const lucide = LUCIDE_PACK_ICONS[icon.icon_emoji_id];
  if (lucide) return <Icon iconNode={lucide.node} size={size} className="shrink-0" />;
  return <EmojiByThumbnail id={icon.icon_emoji_id} glyph={icon.icon_emoji_fallback ?? ""} size={size} />;
}
