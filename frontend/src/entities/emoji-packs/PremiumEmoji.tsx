// light canvas build: no expressions and no eval(); Telegram emoji never use expressions
import lottie from "lottie-web/build/player/lottie_light_canvas";
import { Smile } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import {
  emojiAnimationUrl,
  emojiThumbnailUrl,
  type EmojiPackItem,
} from "@entities/emoji-packs/api";

interface PremiumEmojiProps {
  /** undefined for an empty pack's cover (`pack.items[0]`): drawn as a plain smiley */
  item: EmojiPackItem | undefined;
  /** Rendered size in px; the source artwork is always 512x512. */
  size: number;
}

/** Telegram's own artwork: a lottie animation or a .webm, the static thumbnail
 * while it loads (or for a pack imported before animations were stored), and
 * the plain glyph as the last resort. Every emoji in an open pack animates at
 * once, as in Telegram; pause off-screen ones if a large pack stutters. */
export function PremiumEmoji({ item, size }: PremiumEmojiProps) {
  const [failed, setFailed] = useState(false);
  const container = useRef<HTMLDivElement>(null);
  const isLottie = item?.animation_kind === "lottie";
  const emojiId = item?.custom_emoji_id;

  useEffect(() => {
    if (!emojiId || !isLottie || container.current === null) return;
    const animation = lottie.loadAnimation({
      container: container.current,
      renderer: "canvas",
      loop: true,
      autoplay: true,
      path: emojiAnimationUrl(emojiId),
      // dpr defaults to devicePixelRatio, so a 22px emoji rasterizes the whole
      // vector scene into a 44x44 canvas every frame on a Retina display.
      rendererSettings: { dpr: 1 },
    });
    // with subframes (the default) the frame number stays fractional, the
    // renderer's "same frame" skip never fires and a 30fps animation redraws
    // at 120Hz
    animation.setSubframe(false);
    return () => animation.destroy();
  }, [isLottie, emojiId]);

  if (!item) return <Smile className="text-muted-foreground" style={{ width: size, height: size }} />;
  if (isLottie) return <div ref={container} style={{ width: size, height: size }} />;

  if (item.animation_kind === "video") {
    return (
      <video
        src={emojiAnimationUrl(item.custom_emoji_id)}
        autoPlay
        loop
        muted
        playsInline
        width={size}
        height={size}
        className="object-contain"
      />
    );
  }

  if (failed) return <>{item.fallback_emoji}</>;
  return (
    <img
      src={emojiThumbnailUrl(item.custom_emoji_id)}
      alt={item.fallback_emoji}
      loading="lazy"
      draggable={false}
      onError={() => setFailed(true)}
      width={size}
      height={size}
      className="object-contain"
    />
  );
}
