import { Loader2, Plus, Smile, Trash2 } from "lucide-react";
import { motion } from "motion/react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import {
  deleteEmojiPack,
  importEmojiPack,
  listEmojiPacks,
  type EmojiPack,
} from "@entities/emoji-packs/api";
import { usePermissions } from "@entities/user/use-current-user";
import { getErrorMessage } from "@shared/api/http";
import { bounceTap } from "@shared/lib/bounceState";
import { EMOJI_PACKS_ANCHOR_ID } from "@shared/lib/emoji-packs-anchor";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { EmojiPackDialog } from "@features/emoji-packs/EmojiPackDialog";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { EmptyState } from "@shared/ui/EmptyState";
import { PremiumEmoji } from "@entities/emoji-packs/PremiumEmoji";
import { Spinner } from "@shared/ui/Spinner";
import { Button } from "@shared/ui/Button";
import { Tag } from "@shared/ui/Tag";
import { TextInput } from "@shared/ui/TextInput";
import { Card } from "@shared/ui/Card";
import { CardHeader } from "@shared/ui/CardHeader";

// mirrors backend emoji_packs/telegram_api.py's _SET_NAME_RE: a t.me/addemoji link or the bare set name
const SET_LINK_RE = /^(?:https?:\/\/)?(?:t\.me\/addemoji\/)?[A-Za-z0-9_]{1,64}\/?(?:\?.*)?$/;

export function EmojiPacksManager() {
  const { t } = useTranslation();
  const [packsState, reloadPacks] = useAsyncResource(listEmojiPacks);
  const [link, setLink] = useState("");
  const [isImporting, setIsImporting] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<EmojiPack | null>(null);
  const [openPack, setOpenPack] = useState<EmojiPack | null>(null);

  const permissions = usePermissions();
  const canImport = permissions.includes("EMOJI_PACKS_IMPORT");
  const canDelete = permissions.includes("EMOJI_PACKS_DELETE");

  const isLinkInvalid = link.trim() !== "" && !SET_LINK_RE.test(link.trim());

  const handleImport = async () => {
    setIsImporting(true);
    try {
      const pack = await importEmojiPack(link.trim());
      reloadPacks();
      setLink("");
      toast.success(t("dialogs.emojiPacks.imported", { title: pack.set_name }));
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
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
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    }
  };

  return (
    <Card id={EMOJI_PACKS_ANCHOR_ID}>
      <CardHeader icon={Smile} title={t("dialogs.emojiPacks.title")} description={t("dialogs.emojiPacks.description")} />

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        {canImport && (
          <div className="flex w-full min-w-0 flex-col gap-1">
            <div className="flex w-full min-w-0 gap-2">
              <TextInput
                type="text"
                value={link}
                onChange={(event) => setLink(event.target.value)}
                placeholder={t("dialogs.emojiPacks.linkPlaceholder")}
                aria-invalid={isLinkInvalid}
                className="min-w-0 flex-1"
              />
              <Button
                variant="accent"
                size="field"
                type="button"
                disabled={isImporting || link.trim() === "" || isLinkInvalid}
                onClick={() => void handleImport()}
              >
                {isImporting ? (
                  <Loader2 className="size-3.5 animate-spin" />
                ) : (
                  <Plus className="size-3.5" />
                )}
                {isImporting ? t("dialogs.emojiPacks.adding") : t("common.add")}
              </Button>
            </div>
            {isLinkInvalid && (
              <p id="emoji-pack-link-error" className="text-[12px] text-error">
                {t("dialogs.emojiPacks.linkInvalid")}
              </p>
            )}
          </div>
        )}
      </div>

      <div className="-mx-2 mt-4 max-h-[72vh] overflow-y-auto">
        {packsState.kind === "loading" && <Spinner size="card" />}
        {packsState.kind === "error" && (
          <p className="px-2 text-sm text-error">{t("dialogs.emojiPacks.loadError")}</p>
        )}
        {packsState.kind === "ready" && packsState.data.length === 0 && (
          <EmptyState text={t("dialogs.emojiPacks.empty")} />
        )}
        {packsState.kind === "ready" && packsState.data.length > 0 && (
          <div className="flex flex-col divide-y divide-border/50 px-2">
            {packsState.data.map((pack) => (
              <motion.div
                key={pack.set_name}
                tabIndex={0}
                onClick={() => setOpenPack(pack)}
                onKeyDown={(event) => {
                  if (event.key !== "Enter" && event.key !== " ") return;
                  event.preventDefault();
                  setOpenPack(pack);
                }}
                {...bounceTap(0.03)}
                className="flex cursor-pointer items-center gap-3 rounded-full px-[12.5px] py-2.5 transition-colors hover:bg-white/[0.04]"
              >
                <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-white/[0.06]">
                  <PremiumEmoji item={pack.items[0]} size={18} />
                </div>
                <div className="flex min-w-0 flex-1 items-center gap-2">
                  <p className="truncate text-[13px] font-medium text-foreground">{pack.set_name}</p>
                  <Tag>
                    {pack.items.length}
                  </Tag>
                </div>
                {canDelete && (
                  <button
                    type="button"
                    onClick={(event) => {
                      event.stopPropagation();
                      setPendingDelete(pack);
                    }}
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
          title={t("dialogs.emojiPacks.deleteTitle")}
          message={t("dialogs.emojiPacks.deleteConfirm", { title: pendingDelete.set_name })}
          confirmLabel={t("dialogs.emojiPacks.deleteConfirmButton")}
          cancelLabel={t("common.cancel")}
          danger
          onConfirm={() => void handleDelete(pendingDelete)}
          onCancel={() => setPendingDelete(null)}
        />
      )}
    </Card>
  );
}
