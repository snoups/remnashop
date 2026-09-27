import { Check, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import type { EmojiPack } from "@entities/emoji-packs/api";
import { Modal, useModalClose } from "@shared/ui/Modal";
import { PremiumEmoji } from "@shared/ui/PremiumEmoji";

const COPIED_MS = 1200;

interface EmojiPackDialogProps {
  pack: EmojiPack;
  onClose: () => void;
}

export function EmojiPackDialog({ pack, onClose }: EmojiPackDialogProps) {
  return (
    <Modal onClose={onClose} size="lg" scrollable>
      <EmojiPackDialogBody pack={pack} />
    </Modal>
  );
}

function EmojiPackDialogBody({ pack }: Pick<EmojiPackDialogProps, "pack">) {
  const { t } = useTranslation();
  const close = useModalClose();
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout>>(null);

  useEffect(() => () => clearTimeout(timer.current ?? undefined), []);

  const handleCopy = (customEmojiId: string) => {
    navigator.clipboard
      ?.writeText(customEmojiId)
      .then(() => {
        setCopiedId(customEmojiId);
        clearTimeout(timer.current ?? undefined);
        timer.current = setTimeout(() => setCopiedId(null), COPIED_MS);
      })
      .catch(() => undefined);
  };

  return (
    <>
      <div className="flex shrink-0 items-center justify-between border-b border-border px-5 py-4">
        <h2 className="flex min-w-0 items-center gap-2.5 text-base font-bold text-foreground">
          <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] backdrop-blur-md">
            <PremiumEmoji item={pack.items[0]} size={18} />
          </div>
          <span className="truncate">{pack.set_name}</span>
          <span className="shrink-0 rounded-full bg-white/[0.06] px-2 py-0.5 text-[10.5px] font-semibold tabular-nums text-muted-foreground">
            {pack.items.length}
          </span>
        </h2>
        <button
          type="button"
          onClick={close}
          aria-label={t("dialogs.emojiPacks.close")}
          className="flex size-8 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-white/[0.06] hover:text-foreground"
        >
          <X className="size-4" />
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-5 pb-5 pt-4">
        <div className="grid grid-cols-8 gap-2">
          {pack.items.map((item) => (
            <button
              key={item.custom_emoji_id}
              type="button"
              onClick={() => handleCopy(item.custom_emoji_id)}
              className="flex aspect-square cursor-pointer items-center justify-center rounded-lg transition-colors hover:bg-white/[0.06]"
            >
              {copiedId === item.custom_emoji_id ? (
                <span className="flex items-center gap-1 text-[10.5px] font-semibold text-success">
                  <Check className="size-3.5" />
                </span>
              ) : (
                <PremiumEmoji item={item} size={32} />
              )}
            </button>
          ))}
        </div>
      </div>
    </>
  );
}
