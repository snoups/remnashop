import { Plus, Search, Smile, Trash2, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { deleteEmojiPack, importEmojiPack, listEmojiPacks } from "@entities/emoji-packs/api";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { useCurrentUser } from "@entities/user/use-current-user";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { useClickOutside } from "@shared/lib/use-click-outside";
import { STANDARD_EMOJI } from "@shared/ui/standard-emoji";

/** A standard emoji is a glyph the bot puts in the button's own label; a premium
 * one is an id Telegram renders itself, and only for a bot whose owner has
 * Premium. Exactly one of the two is ever set. */
export type PickedEmoji = { glyph: string } | { customEmojiId: string; fallback: string };

interface EmojiPickerProps {
  /** What to show on the trigger: the glyph, or a premium emoji's fallback. */
  current: string | null;
  disabled?: boolean;
  onPick: (picked: PickedEmoji) => void;
  onClear: () => void;
}

const POPOVER_MOTION = {
  initial: { opacity: 0, scale: 0.96, y: -4 },
  animate: { opacity: 1, scale: 1, y: 0 },
  exit: { opacity: 0, scale: 0.96, y: -4 },
  transition: { duration: 0.15, ease: "easeOut" },
  style: { transformOrigin: "top right" },
} as const;

export function EmojiPicker({ current, disabled = false, onPick, onClear }: EmojiPickerProps) {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);
  const [activeTab, setActiveTab] = useState("standard");
  const ref = useRef<HTMLDivElement>(null);
  const [packsState, reloadPacks] = useAsyncResource(listEmojiPacks);
  const [isAdding, setIsAdding] = useState(false);
  const [link, setLink] = useState("");
  const [isImporting, setIsImporting] = useState(false);
  const [query, setQuery] = useState("");
  const currentUserState = useCurrentUser();
  const permissions =
    currentUserState.kind === "ready" ? currentUserState.data.effective_permissions : [];
  const canImport = permissions.includes("EMOJI_PACKS_IMPORT");
  const canDeletePack = permissions.includes("EMOJI_PACKS_DELETE");
  const packs = packsState.kind === "ready" ? packsState.data : [];

  useClickOutside(ref, isOpen, () => setIsOpen(false));

  const activePack = packs.find((pack) => pack.set_name === activeTab);
  // Unicode names are English, so the search only answers in English -- still
  // better than scrolling seven hundred glyphs.
  const needle = query.trim().toLowerCase();
  const standardGroups = needle
    ? STANDARD_EMOJI.map((group) => ({
        ...group,
        items: group.items.filter((emoji) => emoji.n.includes(needle)),
      })).filter((group) => group.items.length > 0)
    : STANDARD_EMOJI;

  const handleImport = async () => {
    setIsImporting(true);
    try {
      const pack = await importEmojiPack(link.trim());
      reloadPacks();
      setActiveTab(pack.set_name);
      setLink("");
      setIsAdding(false);
    } catch (err) {
      toast.error(getErrorMessage(err, t("auth.errors.genericError")));
    } finally {
      setIsImporting(false);
    }
  };

  const handleDeletePack = async (setName: string) => {
    try {
      await deleteEmojiPack(setName);
      reloadPacks();
      setActiveTab("standard");
    } catch (err) {
      toast.error(getErrorMessage(err, t("auth.errors.genericError")));
    }
  };

  const pick = (picked: PickedEmoji) => {
    onPick(picked);
    setIsOpen(false);
  };

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        disabled={disabled}
        onClick={() => setIsOpen((open) => !open)}
        aria-label={t("dialogs.inspector.emojiPick")}
        className="flex size-[26px] cursor-pointer items-center justify-center rounded-full bg-white/[0.06] text-[14px] transition-colors hover:bg-white/[0.1] disabled:cursor-not-allowed disabled:opacity-40"
      >
        {current ?? <Smile className="size-3.5 text-muted-foreground" />}
      </button>

      <AnimatePresence>
        {isOpen && (
          <motion.div
            {...POPOVER_MOTION}
            className="absolute right-0 top-full z-30 mt-2 w-72 rounded-popover border border-white/[0.14] bg-popover/80 p-2 shadow-[0_24px_48px_-20px_rgba(4,8,20,0.6)] backdrop-blur-2xl"
          >
            <label className="mb-2 flex items-center gap-2 rounded-full border border-border bg-input/60 px-2.5 py-1">
              <Search className="size-3 shrink-0 text-muted-foreground" />
              <input
                type="text"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder={t("dialogs.inspector.emojiSearch")}
                className="min-w-0 flex-1 bg-transparent text-[11.5px] text-foreground outline-none"
              />
            </label>

            <div className="no-scrollbar mb-2 flex gap-1 overflow-x-auto">
              <button
                type="button"
                onClick={() => setActiveTab("standard")}
                className={`shrink-0 cursor-pointer rounded-full px-2.5 py-1 text-[11.5px] transition-colors ${
                  activeTab === "standard" ? "bg-accent text-primary" : "text-foreground/70 hover:bg-white/[0.06]"
                }`}
              >
                {t("dialogs.inspector.emojiStandard")}
              </button>
              {packs.map((pack) => (
                <button
                  key={pack.set_name}
                  type="button"
                  onClick={() => setActiveTab(pack.set_name)}
                  className={`shrink-0 cursor-pointer rounded-full px-2.5 py-1 text-[11.5px] transition-colors ${
                    activeTab === pack.set_name
                      ? "bg-accent text-primary"
                      : "text-foreground/70 hover:bg-white/[0.06]"
                  }`}
                >
                  {pack.title}
                </button>
              ))}
              {canImport && (
                <button
                  type="button"
                  onClick={() => setIsAdding((adding) => !adding)}
                  aria-label={t("dialogs.inspector.emojiAddPack")}
                  className="ml-auto flex size-6 shrink-0 cursor-pointer items-center justify-center rounded-full border border-dashed border-white/[0.16] text-muted-foreground transition-colors hover:bg-white/[0.06]"
                >
                  <Plus className="size-3" />
                </button>
              )}
            </div>

            {isAdding && (
              <div className="mb-2 flex gap-1.5">
                <input
                  type="text"
                  value={link}
                  onChange={(event) => setLink(event.target.value)}
                  placeholder={t("dialogs.inspector.emojiPackLinkPlaceholder")}
                  className="min-w-0 flex-1 rounded-full border border-border bg-input/60 px-2.5 py-1 text-[11.5px] text-foreground outline-none focus:border-primary"
                />
                <button
                  type="button"
                  disabled={isImporting || link.trim() === ""}
                  onClick={() => void handleImport()}
                  className="shrink-0 cursor-pointer rounded-full bg-accent px-2.5 py-1 text-[11.5px] font-semibold text-primary transition-colors hover:bg-primary/20 disabled:opacity-40"
                >
                  {t("dialogs.inspector.emojiPackAdd")}
                </button>
              </div>
            )}

            <div className="max-h-56 overflow-y-auto">
              {activePack ? (
                <>
                  <div className="grid grid-cols-8 gap-1">
                    {activePack.items.map((item) => (
                      <button
                        key={item.custom_emoji_id}
                        type="button"
                        title={item.fallback_emoji}
                        onClick={() =>
                          pick({
                            customEmojiId: item.custom_emoji_id,
                            fallback: item.fallback_emoji,
                          })
                        }
                        className="flex h-7 cursor-pointer items-center justify-center rounded-lg text-[17px] transition-colors hover:bg-white/[0.06]"
                      >
                        {item.fallback_emoji}
                      </button>
                    ))}
                  </div>
                  <div className="mt-2 flex items-start gap-2">
                    <p className="flex-1 text-[11px] leading-relaxed text-muted-foreground">
                      {t("dialogs.inspector.emojiPremiumHint")}
                    </p>
                    {canDeletePack && (
                      <button
                        type="button"
                        onClick={() => void handleDeletePack(activePack.set_name)}
                        aria-label={t("dialogs.inspector.emojiPackDelete")}
                        className="flex size-6 shrink-0 cursor-pointer items-center justify-center rounded-full border border-error/20 bg-error/[0.08] text-error transition-colors hover:bg-error/15"
                      >
                        <Trash2 className="size-3" />
                      </button>
                    )}
                  </div>
                </>
              ) : (
                standardGroups.map((group) => (
                  <div key={group.key} className="mb-2">
                    <span className="mb-1 block text-[10.5px] font-semibold uppercase tracking-wide text-muted-foreground">
                      {t(`dialogs.inspector.emojiGroup.${group.key}`)}
                    </span>
                    <div className="grid grid-cols-8 gap-1">
                      {group.items.map((emoji) => (
                        <button
                          key={emoji.g}
                          type="button"
                          title={emoji.n}
                          onClick={() => pick({ glyph: emoji.g })}
                          className="flex h-7 cursor-pointer items-center justify-center rounded-lg text-[17px] transition-colors hover:bg-white/[0.06]"
                        >
                          {emoji.g}
                        </button>
                      ))}
                    </div>
                  </div>
                ))
              )}
            </div>

            {current !== null && (
              <button
                type="button"
                onClick={() => {
                  onClear();
                  setIsOpen(false);
                }}
                className="mt-1 flex w-full cursor-pointer items-center justify-center gap-1.5 rounded-full border border-border py-1 text-[11.5px] text-foreground/70 transition-colors hover:bg-white/[0.06]"
              >
                <X className="size-3" />
                {t("dialogs.inspector.emojiClear")}
              </button>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
