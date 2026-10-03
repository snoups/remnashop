import { Check } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import type { EmojiPack } from "@entities/emoji-packs/api";
import { copyToClipboard } from "@shared/lib/clipboard";
import { Modal } from "@shared/ui/Modal";
import { PremiumEmoji } from "@entities/emoji-packs/PremiumEmoji";
import { DialogHeader } from "@shared/ui/DialogHeader";
import { Tag } from "@shared/ui/Tag";

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
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout>>(null);

  useEffect(() => () => clearTimeout(timer.current ?? undefined), []);

  const handleCopy = (customEmojiId: string) => {
    void copyToClipboard(customEmojiId).then((copied) => {
      if (!copied) return;
      setCopiedId(customEmojiId);
      clearTimeout(timer.current ?? undefined);
      timer.current = setTimeout(() => setCopiedId(null), COPIED_MS);
    });
  };

  return (
    <>
      <DialogHeader
        glyph={<PremiumEmoji item={pack.items[0]} size={18} />}
        title={pack.set_name}
        badges={
          <Tag>
            {pack.items.length}
          </Tag>
        }
      />

      <div className="scroll-fade-y min-h-0 flex-1 overflow-y-auto px-5 pb-5 pt-4">
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
