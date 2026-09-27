import { BASE_URL, apiDelete, apiGet, apiPost } from "@shared/api/http";

export interface EmojiPackItem {
  custom_emoji_id: string;
  /** The plain emoji Telegram shows in place of this one; drawn when the
   * artwork is missing. */
  fallback_emoji: string;
  animation_kind: "lottie" | "video" | null;
}

export interface EmojiPack {
  set_name: string;
  title: string;
  items: EmojiPackItem[];
}

export function listEmojiPacks(signal?: AbortSignal): Promise<EmojiPack[]> {
  return apiGet<EmojiPack[]>("/emoji-packs", signal);
}

export function importEmojiPack(link: string): Promise<EmojiPack> {
  return apiPost<EmojiPack, { link: string }>("/emoji-packs", { link });
}

export function deleteEmojiPack(setName: string): Promise<null> {
  return apiDelete<null>(`/emoji-packs/${setName}`);
}

/** The pack's real artwork, served as a static thumbnail: sessionless, so an
 * <img> can point straight at it. */
export function emojiThumbnailUrl(customEmojiId: string): string {
  return `${BASE_URL}/emoji-packs/thumbnails/${customEmojiId}`;
}

/** The animation itself: gzipped lottie JSON, or a .webm. */
export function emojiAnimationUrl(customEmojiId: string): string {
  return `${BASE_URL}/emoji-packs/animations/${customEmojiId}`;
}
