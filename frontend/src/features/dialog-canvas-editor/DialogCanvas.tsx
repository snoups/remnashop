import { useTranslation } from "react-i18next";

import type { DialogButtonItem, DialogWindow } from "@entities/dialogs/api";
import type { Selection } from "@features/dialog-canvas-editor/DialogCanvasEditor";
import { ButtonGrid } from "@features/dialog-canvas-editor/ButtonGrid";

interface DialogCanvasProps {
  window: DialogWindow;
  buttons: DialogButtonItem[];
  textByKey: Record<string, string>;
  bannerUrl: string | null;
  selection: Selection | null;
  onSelect: (selection: Selection, anchor: HTMLElement) => void;
  canEditButtons: boolean;
  onReorderButtons: (next: DialogButtonItem[]) => void;
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
}: DialogCanvasProps) {
  const { t } = useTranslation();

  return (
    <div className="mx-auto w-full max-w-sm overflow-hidden rounded-2xl border border-white/[0.08] bg-white/[0.03]">
      <button
        type="button"
        onClick={(event) => onSelect({ kind: "window" }, event.currentTarget)}
        className={`flex h-32 w-full items-center justify-center border-b border-dashed border-white/[0.12] bg-white/[0.02] ${
          selection?.kind === "window" ? "ring-2 ring-inset ring-primary" : ""
        }`}
      >
        {bannerUrl ? (
          <img src={bannerUrl} alt="" className="size-full object-cover" />
        ) : (
          <span className="text-[12.5px] text-muted-foreground">{t("dialogs.canvas.noBanner")}</span>
        )}
      </button>
      <button
        type="button"
        onClick={(event) => onSelect({ kind: "text" }, event.currentTarget)}
        className={`block w-full whitespace-pre-line px-3 py-2.5 text-left text-[13.5px] leading-relaxed text-foreground ${
          selection?.kind === "text" ? "ring-2 ring-inset ring-primary" : ""
        }`}
      >
        {window.text_keys[0] && textByKey[window.text_keys[0]] ? (
          textByKey[window.text_keys[0]]
        ) : (
          <span className="text-muted-foreground">{t("dialogs.canvas.noText")}</span>
        )}
      </button>
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
