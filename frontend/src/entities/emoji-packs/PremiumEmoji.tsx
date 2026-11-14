// light canvas build: no expressions and no eval(); Telegram emoji never use expressions
import lottie from "lottie-web/build/player/lottie_light_canvas";
import { Icon, Smile } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import {
  emojiAnimationUrl,
  emojiThumbnailUrl,
  type EmojiPackItem,
} from "@entities/emoji-packs/api";
import { LUCIDE_PACK_ICONS } from "@entities/emoji-packs/lucide-pack";

interface PremiumEmojiProps {
  /** undefined for an empty pack's cover (`pack.items[0]`): drawn as a plain smiley */
  item: EmojiPackItem | undefined;
  /** Rendered size in px; the source artwork is always 512x512. */
  size: number;
  /** A cell of a pack's grid: the thumbnail at rest, animated only while the
   * pointer is over the cell. Dozens of lottie scenes on screen at once drop
   * the page to 30fps and below. */
  still?: boolean;
}

// an animation starts a little before its cell scrolls into view
const IN_VIEW_MARGIN = "64px";

/** Telegram's artwork: a lottie animation or a .webm while on screen, the
 * static thumbnail off screen, while it loads, or for a pack imported before
 * animations were stored, and the plain glyph as the last resort. A pack holds
 * up to a thousand emoji: animating them all at once stalls the page. */
export function PremiumEmoji({ item, size, still = false }: PremiumEmojiProps) {
  const [failed, setFailed] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [animationReady, setAnimationReady] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const container = useRef<HTMLDivElement>(null);
  const isLottie = item?.animation_kind === "lottie";
  const isAnimated = isLottie || item?.animation_kind === "video";
  const emojiId = item?.custom_emoji_id;

  useEffect(() => {
    const cell = box.current?.parentElement;
    if (!isAnimated || !still || !cell) return;
    const start = () => setPlaying(true);
    const stop = () => setPlaying(false);
    cell.addEventListener("pointerenter", start);
    cell.addEventListener("pointerleave", stop);
    return () => {
      cell.removeEventListener("pointerenter", start);
      cell.removeEventListener("pointerleave", stop);
    };
  }, [isAnimated, still]);

  useEffect(() => {
    if (!isAnimated || still || box.current === null) return;
    // the observer honours overflow clipping, so a cell scrolled out of a
    // popover or dialog counts as hidden
    const observer = new IntersectionObserver(([entry]) => setPlaying(entry.isIntersecting), {
      rootMargin: IN_VIEW_MARGIN,
    });
    observer.observe(box.current);
    return () => observer.disconnect();
  }, [isAnimated, still]);

  useEffect(() => {
    if (!emojiId || !isLottie || !playing || container.current === null) return;
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
    animation.addEventListener("DOMLoaded", () => setAnimationReady(true));
    return () => {
      animation.destroy();
      setAnimationReady(false);
    };
  }, [isLottie, emojiId, playing]);

  if (!item) return <Smile className="text-muted-foreground" style={{ width: size, height: size }} />;
  const lucide = LUCIDE_PACK_ICONS[item.custom_emoji_id];
  if (lucide) return <Icon iconNode={lucide.node} size={size} color="white" />;

  const thumbnail = failed ? (
    <>{item.fallback_emoji}</>
  ) : (
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
  if (!isAnimated) return thumbnail;

  return (
    <div ref={box} className="relative flex items-center justify-center" style={{ width: size, height: size }}>
      {/* lottie empties its container on destroy: it gets one React never renders into */}
      {isLottie && <div ref={container} className="absolute inset-0" />}
      {!isLottie && playing ? (
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
      ) : (
        !animationReady && thumbnail
      )}
    </div>
  );
}
