import { Inbox, Loader2, Plus, Smile, Trash2 } from "lucide-react";
import { motion } from "motion/react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import {
  deleteEmojiPack,
  importEmojiPack,
  listEmojiPacks,
  type EmojiPack,
} from "@entities/emoji-packs/api";
import { useCurrentUser } from "@entities/user/use-current-user";
import { getErrorMessage } from "@shared/api/http";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { EMOJI_PACKS_ANCHOR_ID } from "@shared/lib/emoji-packs-anchor";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { EmojiPackDialog } from "@features/emoji-packs/EmojiPackDialog";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { PremiumEmoji } from "@shared/ui/PremiumEmoji";
import { Spinner } from "@shared/ui/Spinner";

export function EmojiPacksManager() {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const [packsState, reloadPacks] = useAsyncResource(listEmojiPacks);
  const [link, setLink] = useState("");
  const [isImporting, setIsImporting] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<EmojiPack | null>(null);
  const [openPack, setOpenPack] = useState<EmojiPack | null>(null);

  const currentUserState = useCurrentUser();
  const permissions =
    currentUserState.kind === "ready" ? currentUserState.data.effective_permissions : [];
  const canImport = permissions.includes("EMOJI_PACKS_IMPORT");
  const canDelete = permissions.includes("EMOJI_PACKS_DELETE");

  const handleImport = async () => {
    setIsImporting(true);
    try {
      const pack = await importEmojiPack(link.trim());
      reloadPacks();
      setLink("");
      toast.success(t("dialogs.emojiPacks.imported", { title: pack.set_name }));
    } catch (err) {
      toast.error(getErrorMessage(err, t("auth.errors.genericError")));
    } finally {
      setIsImporting(false);
    }
  };

  const handleDelete = async (pack: EmojiPack) => {
    setPendingDelete(null);
    try {
      await deleteEmojiPack(pack.set_name);
      reloadPacks();
    } catch (err) {
      toast.error(getErrorMessage(err, t("auth.errors.genericError")));
    }
  };

  return (
    <div
      id={EMOJI_PACKS_ANCHOR_ID}
      className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-4"
    >
      <div className="flex items-center gap-2.5">
        <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] text-foreground backdrop-blur-md">
          <Smile className="size-4" />
        </div>
        <div>
          <h2 className="text-sm font-bold text-foreground">{t("dialogs.emojiPacks.title")}</h2>
          <p className="mt-0.5 text-[12.5px] text-muted-foreground">
            {t("dialogs.emojiPacks.description")}
          </p>
        </div>
      </div>

      <div className="-mx-4 mt-4 border-t border-white/[0.07]" />

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        {canImport && (
          <div className="flex w-full min-w-0 gap-2">
            <input
              type="text"
              value={link}
              onChange={(event) => setLink(event.target.value)}
              placeholder={t("dialogs.emojiPacks.linkPlaceholder")}
              className="min-w-0 flex-1 rounded-xl border border-border bg-input/60 px-3 py-2 text-sm text-foreground outline-none transition-colors focus:border-primary"
            />
            <motion.button
              type="button"
              disabled={isImporting || link.trim() === ""}
              onClick={() => void handleImport()}
              {...bounceTap(bounceStrength)}
              className="flex shrink-0 cursor-pointer items-center gap-1.5 rounded-full border border-transparent bg-accent px-4 py-2 text-sm font-medium text-primary transition-colors hover:bg-primary/20 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isImporting ? (
                <Loader2 className="size-3.5 animate-spin" />
              ) : (
                <Plus className="size-3.5" />
              )}
              {isImporting ? t("dialogs.emojiPacks.adding") : t("dialogs.emojiPacks.add")}
            </motion.button>
          </div>
        )}
      </div>

      <div className="-mx-2 mt-4 max-h-[72vh] overflow-y-auto">
        {packsState.kind === "loading" && <Spinner className="py-10" />}
        {packsState.kind === "error" && (
          <p className="px-2 text-sm text-error">{t("dialogs.emojiPacks.loadError")}</p>
        )}
        {packsState.kind === "ready" && packsState.data.length === 0 && (
          <div className="flex flex-col items-center gap-2 py-10 text-muted-foreground">
            <Inbox className="size-5" />
            <p className="text-sm">{t("dialogs.emojiPacks.empty")}</p>
          </div>
        )}
        {packsState.kind === "ready" && packsState.data.length > 0 && (
          <div className="flex flex-col divide-y divide-border/50 px-2">
            {packsState.data.map((pack) => (
              <motion.div
                key={pack.set_name}
                role="button"
                tabIndex={0}
                onClick={() => setOpenPack(pack)}
                onKeyDown={(event) => {
                  if (event.key !== "Enter" && event.key !== " ") return;
                  event.preventDefault();
                  setOpenPack(pack);
                }}
                {...bounceTap(bounceStrength, 0.03)}
                className="flex cursor-pointer items-center gap-3 rounded-full px-[12.5px] py-2.5 transition-colors hover:bg-white/[0.04]"
              >
                <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-white/[0.06]">
                  <PremiumEmoji item={pack.items[0]} size={18} />
                </div>
                <div className="flex min-w-0 flex-1 items-center gap-2">
                  <p className="truncate text-[13px] font-medium text-foreground">{pack.set_name}</p>
                  <span className="shrink-0 rounded-full bg-white/[0.06] px-2 py-0.5 text-[10.5px] tabular-nums text-muted-foreground">
                    {pack.items.length}
                  </span>
                </div>
                {canDelete && (
                  <button
                    type="button"
                    onClick={(event) => {
                      event.stopPropagation();
                      setPendingDelete(pack);
                    }}
                    aria-label={t("dialogs.emojiPacks.delete")}
                    className="flex size-7 shrink-0 cursor-pointer items-center justify-center rounded-full bg-error/[0.08] text-error transition-colors hover:bg-error/15"
                  >
                    <Trash2 className="size-3.5" />
                  </button>
                )}
              </motion.div>
            ))}
          </div>
        )}
      </div>

      {openPack && <EmojiPackDialog pack={openPack} onClose={() => setOpenPack(null)} />}

      {pendingDelete && (
        <ConfirmDialog
          title={t("dialogs.emojiPacks.delete")}
          message={t("dialogs.emojiPacks.deleteConfirm", { title: pendingDelete.set_name })}
          confirmLabel={t("dialogs.emojiPacks.deleteConfirmButton")}
          cancelLabel={t("dialogs.windowList.deleteWindowCancelButton")}
          danger
          onConfirm={() => void handleDelete(pendingDelete)}
          onCancel={() => setPendingDelete(null)}
        />
      )}
    </div>
  );
}
