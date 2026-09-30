import { useState } from "react";

import { splitPremiumEmoji } from "@entities/dialogs/api";
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

/** Dialog text with premium emoji markup drawn as the emoji itself. */
export function EmojiText({ value }: { value: string }) {
  return (
    <>
      {splitPremiumEmoji(value).map((part, index) =>
        typeof part === "string" ? (
          part
        ) : (
          <EmojiThumbnail key={index} glyph={part.glyph} customEmojiId={part.customEmojiId} />
        ),
      )}
    </>
  );
}
