// light canvas build: no expressions support, and no eval() -- Telegram emoji never use expressions
import lottie from "lottie-web/build/player/lottie_light_canvas";
import { useEffect, useRef, useState } from "react";

import {
  emojiAnimationUrl,
  emojiThumbnailUrl,
  type EmojiPackItem,
} from "@entities/emoji-packs/api";

interface PremiumEmojiProps {
  item: EmojiPackItem;
  /** Rendered size in px; the source artwork is always 512x512. */
  size: number;
}

/** Telegram's own artwork: a lottie animation, a .webm, or -- while either
 * loads, or for a pack imported before they were stored -- the static
 * thumbnail, falling back again to the plain glyph.
 * every emoji in an open pack animates at once, which is what
 * Telegram does too; pause off-screen ones if a large pack ever stutters. */
export function PremiumEmoji({ item, size }: PremiumEmojiProps) {
  const [failed, setFailed] = useState(false);
  const container = useRef<HTMLDivElement>(null);
  const isLottie = item.animation_kind === "lottie";

  useEffect(() => {
    if (!isLottie || container.current === null) return;
    const animation = lottie.loadAnimation({
      container: container.current,
      renderer: "canvas",
      loop: true,
      autoplay: true,
      path: emojiAnimationUrl(item.custom_emoji_id),
      // dpr defaults to devicePixelRatio, so a 22px emoji rasterizes the whole
      // vector scene into a 44x44 canvas every frame on a Retina display.
      rendererSettings: { dpr: 1 },
    });
    // Subframe rendering is on by default, which keeps the frame number
    // fractional -- the canvas renderer's "same frame, skip the draw" guard
    // then never matches, and a 30fps animation redraws at the display's
    // 120Hz. Integer frames let it skip.
    animation.setSubframe(false);
    return () => animation.destroy();
  }, [isLottie, item.custom_emoji_id]);

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
