import { useTranslation } from "react-i18next";

import { iconIdTextKey, iconTextKey, splitTextKey } from "@entities/dialogs/api";
import { EmojiPicker, type PickedEmoji } from "@entities/emoji-packs/EmojiPicker";
import type { TranslationEntry } from "@entities/translations/api";
import { EmojiThumbnail } from "@features/dialog-canvas-editor/EmojiThumbnail";
import type { SaveText } from "@features/dialog-canvas-editor/TextEditorPanel";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";

interface ButtonIconPickerProps {
  textKey: string;
  entries: TranslationEntry[];
  activeLocale: string;
  disabled: boolean;
  save: SaveText;
  onSaved: (entry: TranslationEntry) => void;
}

/** A button label's icon: a glyph rides in the label text, a premium id goes to
 * Telegram's icon field and the glyph stays as its fallback. */
export function ButtonIconPicker({ textKey, entries, activeLocale, disabled, save, onSaved }: ButtonIconPickerProps) {
  const { t } = useTranslation();

  const valueOf = (key: string): string => {
    const { messageId, attributeId } = splitTextKey(key);
    return (
      entries.find((e) => e.locale === activeLocale && e.message_id === messageId && e.attribute_id === attributeId)
        ?.value ?? ""
    );
  };
  const glyph = valueOf(iconTextKey(textKey));
  const iconId = valueOf(iconIdTextKey(textKey));

  const write = async (key: string, value: string) => {
    const { messageId, attributeId } = splitTextKey(key);
    const updated = await save(activeLocale, messageId, attributeId, value);
    onSaved({
      locale: updated.locale,
      message_id: updated.message_id,
      attribute_id: attributeId,
      value: updated.value,
      default_value: updated.default_value,
    });
  };

  const handlePick = async (picked: PickedEmoji) => {
    try {
      if ("glyph" in picked) {
        await write(iconTextKey(textKey), picked.glyph);
        if (iconId) await write(iconIdTextKey(textKey), "");
      } else {
        await write(iconIdTextKey(textKey), picked.customEmojiId);
        await write(iconTextKey(textKey), picked.fallback);
      }
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    }
  };

  return (
    <EmojiPicker
      current={iconId ? <EmojiThumbnail glyph={glyph} customEmojiId={iconId} /> : glyph || null}
      disabled={disabled}
      onPick={(picked) => void handlePick(picked)}
      onClear={() => void handlePick({ glyph: "" })}
    />
  );
}
