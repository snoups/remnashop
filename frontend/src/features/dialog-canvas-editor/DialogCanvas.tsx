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
  /** 448px instead of 384px: the window list is folded away and the preview takes its room */
  wide?: boolean;
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
  wide = false,
}: DialogCanvasProps) {
  const { t } = useTranslation();

  return (
    <div className={`w-full ${wide ? "max-w-md" : "max-w-sm"} rounded-2xl max-md:rounded-card border border-white/[0.08] bg-white/[0.03] p-2.5`}>
      <div className="flex flex-col gap-1.5">
        {/* Preview only; the banner is picked on the inspector's window tab.
            No fixed height and no object-cover: whatever was uploaded shows
            whole, in its own ratio, the way Telegram sends it. */}
        {bannerUrl ? (
          <img src={bannerUrl} alt="" className="block w-full rounded-xl" />
        ) : (
          <div className="flex aspect-video w-full items-center justify-center rounded-xl border border-dashed border-white/[0.12] bg-white/[0.02]">
            <span className="text-[12.5px] text-muted-foreground">{t("dialogs.canvas.noBanner")}</span>
          </div>
        )}
        <Pressable
          type="button"
          onClick={() => onSelect({ kind: "text" })}
          className={`block w-full cursor-pointer whitespace-pre-line rounded-lg px-2.5 py-2 text-left text-[13px] leading-relaxed text-foreground transition-colors ${
            selection?.kind === "text" ? "ring-2 ring-inset ring-primary" : "hover:bg-white/[0.06]"
          }`}
        >
          {window.text_keys[0] && textByKey[window.text_keys[0]] ? (
            <TelegramHtml value={textByKey[window.text_keys[0]]} />
          ) : (
            <span className="text-muted-foreground">{t("dialogs.canvas.noText")}</span>
          )}
        </Pressable>
      </div>
      <div className="my-2.5 h-px bg-white/[0.08]" />
      <ButtonGrid
        buttons={buttons}
        textByKey={textByKey}
        selection={selection}
        onSelect={onSelect}
        emptyLabel={t("dialogs.canvas.emptyButtons")}
        canEdit={canEditButtons}
        onReorder={onReorderButtons}
      />
    </div>
  );
}
