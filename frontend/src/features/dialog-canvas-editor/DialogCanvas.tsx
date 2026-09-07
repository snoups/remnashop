import { useTranslation } from "react-i18next";

import type { DialogButtonItem, DialogWindow } from "@entities/dialogs/api";

interface DialogCanvasProps {
  window: DialogWindow;
  textByKey: Record<string, string>;
  bannerUrl: string | null;
}

function buttonRows(buttons: DialogButtonItem[]): DialogButtonItem[][] {
  const byRow = new Map<number, DialogButtonItem[]>();
  for (const button of buttons) {
    const row = byRow.get(button.row) ?? [];
    row.push(button);
    byRow.set(button.row, row);
  }
  return [...byRow.entries()]
    .sort(([a], [b]) => a - b)
    .map(([, row]) => row.sort((a, b) => a.column - b.column));
}

const STYLE_BORDER_CLASSNAME: Record<string, string> = {
  primary: "border-primary/50",
  success: "border-emerald-500/60",
  danger: "border-red-500/60",
};

function CanvasButton({ button, textByKey }: { button: DialogButtonItem; textByKey: Record<string, string> }) {
  const label = textByKey[button.text_key] ?? button.text_key;
  const borderClassName = button.style ? STYLE_BORDER_CLASSNAME[button.style] : "border-white/[0.12]";

  return (
    <div
      className={`flex flex-1 items-center justify-center gap-1.5 rounded-lg border px-3 py-2 text-center text-[13px] ${borderClassName} ${
        button.is_hidden ? "opacity-40" : ""
      }`}
    >
      {button.icon_custom_emoji_id ? <span className="text-[11px] opacity-70">★</span> : null}
      <span className="truncate">{label}</span>
    </div>
  );
}

export function DialogCanvas({ window, textByKey, bannerUrl }: DialogCanvasProps) {
  const { t } = useTranslation();
  const messageText = window.text_keys[0] ? textByKey[window.text_keys[0]] : undefined;
  const rows = buttonRows(window.buttons);

  return (
    <div className="mx-auto w-full max-w-sm overflow-hidden rounded-2xl border border-white/[0.08] bg-white/[0.03]">
      <div className="flex h-32 items-center justify-center border-b border-dashed border-white/[0.12] bg-white/[0.02]">
        {bannerUrl ? (
          <img src={bannerUrl} alt="" className="size-full object-cover" />
        ) : (
          <span className="text-[12.5px] text-muted-foreground">{t("dialogs.canvas.noBanner")}</span>
        )}
      </div>
      <div className="whitespace-pre-line px-3 py-2.5 text-[13.5px] leading-relaxed text-foreground">
        {messageText || <span className="text-muted-foreground">{t("dialogs.canvas.noText")}</span>}
      </div>
      <div className="flex flex-col gap-1.5 px-3 pb-3">
        {rows.length === 0 ? (
          <p className="text-[12px] text-muted-foreground">{t("dialogs.canvas.emptyButtons")}</p>
        ) : (
          rows.map((row, index) => (
            <div key={index} className="flex gap-1.5">
              {row.map((button) => (
                <CanvasButton key={`${button.row}-${button.column}`} button={button} textByKey={textByKey} />
              ))}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
