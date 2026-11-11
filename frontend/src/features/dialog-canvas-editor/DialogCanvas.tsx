import { Plus } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { DialogButtonItem, DialogWindow } from "@entities/dialogs/api";
import type { Selection } from "@features/dialog-canvas-editor/DialogCanvasEditor";
import { ButtonGrid } from "@features/dialog-canvas-editor/ButtonGrid";
import { TelegramHtml } from "@features/dialog-canvas-editor/TelegramHtml";
import { Pressable } from "@shared/ui/Pressable";

interface DialogCanvasProps {
  window: DialogWindow;
  buttons: DialogButtonItem[];
  textByKey: Record<string, string>;
  bannerUrl: string | null;
  selection: Selection | null;
  onSelect: (selection: Selection) => void;
  canEditButtons: boolean;
  onReorderButtons: (next: DialogButtonItem[]) => void;
  /** set: a dashed "add a button" under the keyboard */
  onAddButton?: () => void;
}

export function DialogCanvas({
  window,
  buttons,
  textByKey,
  bannerUrl,
  selection,
  onSelect,
  canEditButtons,
  onReorderButtons,
  onAddButton,
}: DialogCanvasProps) {
  const { t } = useTranslation();

  return (
    // a chat backdrop under the message, the way the bot shows it
    <div className="glass-well flex w-full flex-col items-center rounded-2xl bg-[radial-gradient(circle_at_30%_20%,rgb(96_165_250/0.10),transparent_60%)] px-4 py-6">
      <div className="flex w-full max-w-sm flex-col gap-1.5">
        <div
          className={`overflow-hidden rounded-2xl rounded-bl-md border border-white/[0.08] bg-white/[0.06] shadow-lg ${
            window.is_enabled ? "" : "opacity-60"
          }`}
        >
          {/* whatever was uploaded shows whole, in its own ratio, the way Telegram sends it */}
          {bannerUrl && <img src={bannerUrl} alt="" className="block w-full" />}
          <Pressable
            as="div"
            onClick={() => onSelect({ kind: "text" })}
            className={`m-1 cursor-pointer whitespace-pre-line rounded-xl px-2.5 py-2 text-sm leading-relaxed text-foreground transition-colors ${
              selection?.kind === "text" ? "bg-primary/10 ring-1 ring-inset ring-primary" : "hover:bg-white/[0.05]"
            }`}
          >
            {window.text_keys[0] && textByKey[window.text_keys[0]] ? (
              <TelegramHtml value={textByKey[window.text_keys[0]]} />
            ) : (
              <span className="text-muted-foreground">{t("dialogs.canvas.noText")}</span>
            )}
          </Pressable>
        </div>
        <ButtonGrid
          buttons={buttons}
          textByKey={textByKey}
          selection={selection}
          onSelect={onSelect}
          emptyLabel={t("dialogs.canvas.emptyButtons")}
          canEdit={canEditButtons}
          onReorder={onReorderButtons}
        />
        {onAddButton && (
          <Pressable
            type="button"
            onClick={onAddButton}
            className="flex h-10 items-center justify-center gap-1.5 rounded-xl border border-dashed border-white/[0.14] text-sm text-muted-foreground transition-colors hover:bg-white/[0.04] hover:text-foreground"
          >
            <Plus className="size-3.5" />
            {t("dialogs.inspector.buttonAdd")}
          </Pressable>
        )}
      </div>
    </div>
  );
}
