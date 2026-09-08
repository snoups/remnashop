import { useState } from "react";
import { useTranslation } from "react-i18next";

import { BANNER_OPTIONS, type DialogWindow } from "@entities/dialogs/api";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";

interface WindowSwitcherProps {
  windows: DialogWindow[];
  selectedKey: string | null;
  onSelect: (key: string) => void;
  canCreate: boolean;
  canDelete: boolean;
  onCreate: (titleText: string, bannerName: string | null) => void;
  onDelete: (key: string) => void;
}

function WindowChip({
  window,
  isSelected,
  canDelete,
  onSelect,
  onDelete,
}: {
  window: DialogWindow;
  isSelected: boolean;
  canDelete: boolean;
  onSelect: () => void;
  onDelete: () => void;
}) {
  const { t } = useTranslation();
  return (
    <div
      className={`flex items-center gap-0.5 rounded-full border px-1 transition-colors ${
        isSelected ? "border-primary/40 bg-accent" : "border-white/[0.12] hover:bg-white/[0.06]"
      }`}
    >
      <button
        type="button"
        onClick={onSelect}
        className={`whitespace-nowrap px-2.5 py-1.5 text-[12.5px] ${isSelected ? "text-primary" : "text-foreground/80"}`}
      >
        {window.key}
      </button>
      {canDelete && window.kind === "custom" ? (
        <button
          type="button"
          onClick={onDelete}
          aria-label={t("dialogs.windowList.deleteWindow")}
          className="pr-1.5 text-[13px] text-muted-foreground hover:text-error"
        >
          ×
        </button>
      ) : null}
    </div>
  );
}

export function WindowSwitcher({ windows, selectedKey, onSelect, canCreate, canDelete, onCreate, onDelete }: WindowSwitcherProps) {
  const { t } = useTranslation();
  const seedWindows = windows.filter((w) => w.kind === "seed");
  const customWindows = windows.filter((w) => w.kind === "custom");
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [titleText, setTitleText] = useState("");
  const [bannerName, setBannerName] = useState("");

  return (
    <div className="flex flex-1 flex-wrap items-center gap-1.5">
      {seedWindows.map((window) => (
        <WindowChip
          key={window.key}
          window={window}
          isSelected={window.key === selectedKey}
          canDelete={false}
          onSelect={() => onSelect(window.key)}
          onDelete={() => {}}
        />
      ))}
      {customWindows.map((window) => (
        <WindowChip
          key={window.key}
          window={window}
          isSelected={window.key === selectedKey}
          canDelete={canDelete}
          onSelect={() => onSelect(window.key)}
          onDelete={() => setDeleteTarget(window.key)}
        />
      ))}
      {canCreate && (
        <button
          type="button"
          onClick={() => setIsCreateOpen(true)}
          className="whitespace-nowrap rounded-full border border-dashed border-white/[0.12] px-3 py-1.5 text-[12px] text-foreground/70 hover:bg-white/[0.06]"
        >
          {t("dialogs.windowList.addWindow")}
        </button>
      )}
      {isCreateOpen && (
        <ConfirmDialog
          title={t("dialogs.windowList.addWindow")}
          message={t("dialogs.windowList.addWindowMessage")}
          confirmLabel={t("dialogs.windowList.addWindowConfirm")}
          cancelLabel={t("dialogs.windowList.addWindowCancel")}
          onConfirm={() => {
            if (!titleText.trim()) return;
            onCreate(titleText.trim(), bannerName || null);
            setIsCreateOpen(false);
            setTitleText("");
            setBannerName("");
          }}
          onCancel={() => setIsCreateOpen(false)}
        >
          <input
            type="text"
            value={titleText}
            onChange={(event) => setTitleText(event.target.value)}
            placeholder={t("dialogs.windowList.addWindowTitlePlaceholder")}
            className="mb-2 w-full rounded-lg border border-border bg-input/60 px-2.5 py-1.5 text-[13px]"
          />
          <select
            value={bannerName}
            onChange={(event) => setBannerName(event.target.value)}
            className="w-full rounded-lg border border-border bg-input/60 px-2.5 py-1.5 text-[13px]"
          >
            <option value="">{t("dialogs.inspector.bannerNone")}</option>
            {BANNER_OPTIONS.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </ConfirmDialog>
      )}
      {deleteTarget && (
        <ConfirmDialog
          title={t("dialogs.windowList.deleteWindow")}
          message={t("dialogs.windowList.deleteWindowConfirm", { key: deleteTarget })}
          confirmLabel={t("dialogs.windowList.deleteWindowConfirmButton")}
          cancelLabel={t("dialogs.windowList.deleteWindowCancelButton")}
          danger
          onConfirm={() => {
            onDelete(deleteTarget);
            setDeleteTarget(null);
          }}
          onCancel={() => setDeleteTarget(null)}
        />
      )}
    </div>
  );
}
