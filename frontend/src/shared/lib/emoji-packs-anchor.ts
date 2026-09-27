/** The emoji packs panel on the bot settings page -- the picker's "+" scrolls
 * to it, so both sides need the same id. */
export const EMOJI_PACKS_ANCHOR_ID = "emoji-packs";

export function scrollToEmojiPacks(): void {
  document
    .getElementById(EMOJI_PACKS_ANCHOR_ID)
    ?.scrollIntoView({ behavior: "smooth", block: "start" });
}
