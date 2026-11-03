import { Plus, Smile, Trash2 } from "lucide-react";
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
import { EMOJI_PACKS_ANCHOR_ID } from "@shared/lib/emoji-packs-anchor";
import { toast } from "@shared/lib/toast";
import { useFieldValidation } from "@shared/lib/use-field-validation";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { EmojiPackDialog } from "@features/emoji-packs/EmojiPackDialog";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { EmptyState, ErrorState } from "@shared/ui/glass/EmptyState";
import { PremiumEmoji } from "@entities/emoji-packs/PremiumEmoji";
import { Spinner } from "@shared/ui/Spinner";
import { Button } from "@shared/ui/Button";
import { Input } from "@shared/ui/glass/Input";
import { Row } from "@shared/ui/glass/Row";
import { Section, SectionFields, SectionRows } from "@shared/ui/glass/Section";
import { Tag } from "@shared/ui/glass/Tag";
import { IconButton } from "@shared/ui/IconButton";

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

  const validation = useFieldValidation<"link">();
  const linkError = link.trim() !== "" && !SET_LINK_RE.test(link.trim()) ? t("dialogs.emojiPacks.linkInvalid") : null;
  const linkShown = validation.visible("link", linkError);

  const handleImport = async () => {
    validation.submit();
    if (linkError !== null) return;
    setIsImporting(true);
    try {
      const pack = await importEmojiPack(link.trim());
      reloadPacks();
      setLink("");
      validation.reset();
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
    <Section
      id={EMOJI_PACKS_ANCHOR_ID}
      icon={Smile}
      title={t("dialogs.emojiPacks.title")}
      description={t("dialogs.emojiPacks.description")}
    >
      {canImport && (
        <SectionFields>
          <div className="flex flex-col gap-1.5">
            <div className="flex min-w-0 gap-2">
              <Input
                className="flex-1"
                value={link}
                onChange={(event) => setLink(event.target.value)}
                onBlur={validation.touch("link")}
                placeholder={t("dialogs.emojiPacks.linkPlaceholder")}
                aria-invalid={linkShown !== undefined}
              />
              <Button
                variant="glassAccent"
                icon={Plus}
                isLoading={isImporting}
                disabled={link.trim() === ""}
                onClick={() => void handleImport()}
              >
                {isImporting ? t("dialogs.emojiPacks.adding") : t("common.add")}
              </Button>
            </div>
            {linkShown && <p className="text-[12px] text-error">{linkShown}</p>}
          </div>
        </SectionFields>
      )}

      {packsState.kind === "loading" && <Spinner size="card" />}
      {packsState.kind === "error" && <ErrorState text={t("common.loadError")} />}
      {packsState.kind === "ready" && packsState.data.length === 0 && <EmptyState text={t("dialogs.emojiPacks.empty")} />}
      {packsState.kind === "ready" && packsState.data.length > 0 && (
        // a long list scrolls inside the card
        <div className="max-h-[72vh] overflow-y-auto">
          <SectionRows divided={canImport}>
            {packsState.data.map((pack) => (
              <Row
                key={pack.set_name}
                glyph={<PremiumEmoji item={pack.items[0]} size={18} />}
                label={pack.set_name}
                onClick={() => setOpenPack(pack)}
              >
                <Tag subtle>{pack.items.length}</Tag>
                {canDelete && (
                  <IconButton size="8" tone="danger" onClick={() => setPendingDelete(pack)}>
                    <Trash2 className="size-4" />
                  </IconButton>
                )}
              </Row>
            ))}
          </SectionRows>
        </div>
      )}

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
    </Section>
  );
}
