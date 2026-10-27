import { useState } from "react";

import { emojiThumbnailUrl } from "@entities/emoji-packs/api";

export function EmojiThumbnail({ glyph, customEmojiId }: { glyph: string; customEmojiId: string }) {
  const [failed, setFailed] = useState(false);
  if (failed) return <>{glyph}</>;
  return (
    <img
      src={emojiThumbnailUrl(customEmojiId)}
      alt={glyph}
      draggable={false}
      onError={() => setFailed(true)}
      className="inline-block size-[1.25em] align-[-0.25em] object-contain"
    />
  );
}
