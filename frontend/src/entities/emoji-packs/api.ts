import { apiDelete, apiGet, apiPost } from "@shared/api/http";

export interface EmojiPackItem {
  custom_emoji_id: string;
  /** The plain emoji Telegram shows in place of this one -- and all the picker
   * can draw, since the real artwork is an animated .tgs. */
  fallback_emoji: string;
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
