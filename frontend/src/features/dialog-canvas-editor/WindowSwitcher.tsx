import { useTranslation } from "react-i18next";

import type { DialogWindow } from "@entities/dialogs/api";

interface WindowSwitcherProps {
  windows: DialogWindow[];
  selectedKey: string | null;
  onSelect: (key: string) => void;
}

function WindowRow({
  window,
  isSelected,
  onSelect,
}: {
  window: DialogWindow;
  isSelected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={`block w-full truncate rounded-full px-3 py-2 text-left text-[13px] transition-colors ${
        isSelected ? "bg-accent text-primary" : "text-foreground/80 hover:bg-white/[0.06]"
      }`}
    >
      {window.key}
    </button>
  );
}

export function WindowSwitcher({ windows, selectedKey, onSelect }: WindowSwitcherProps) {
  const { t } = useTranslation();
  const seedWindows = windows.filter((w) => w.kind === "seed");
  const customWindows = windows.filter((w) => w.kind === "custom");

  return (
    <div className="flex w-full shrink-0 flex-col gap-3 lg:w-56">
      <div>
        <p className="px-3 pb-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
          {t("dialogs.windowList.seedSection")}
        </p>
        <div className="flex flex-col gap-0.5">
          {seedWindows.map((window) => (
            <WindowRow
              key={window.key}
              window={window}
              isSelected={window.key === selectedKey}
              onSelect={() => onSelect(window.key)}
            />
          ))}
        </div>
      </div>
      <div>
        <p className="px-3 pb-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
          {t("dialogs.windowList.customSection")}
        </p>
        <div className="flex flex-col gap-0.5">
          {customWindows.length === 0 ? (
            <p className="px-3 text-[12.5px] text-muted-foreground">{t("dialogs.windowList.empty")}</p>
          ) : (
            customWindows.map((window) => (
              <WindowRow
                key={window.key}
                window={window}
                isSelected={window.key === selectedKey}
                onSelect={() => onSelect(window.key)}
              />
            ))
          )}
        </div>
      </div>
    </div>
  );
}
