import { ChevronRight, MessageSquare } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import type { DialogFlow, DialogWindow } from "@entities/dialogs/api";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";

interface WindowSwitcherProps {
  windows: DialogWindow[];
  /** Custom windows no button navigates to: unreachable in the bot. */
  unreachableKeys: Set<string>;
  /** The window holding unsaved keyboard edits, if any. */
  dirtyKey: string | null;
  labelOf: (window: DialogWindow) => string;
  selectedKey: string | null;
  onSelect: (key: string) => void;
  canCreate: boolean;
  isLimitReached: boolean;
  canDelete: boolean;
  onCreate: (titleText: string, bannerName: string | null) => void;
  onDelete: (key: string) => void;
}

const LABEL_MAX_LENGTH = 24;

// Windows are grouped by the flow they belong to; custom ones are their own
// branch and sit last.
const FLOW_ORDER: DialogFlow[] = [
  "menu",
  "purchase",
  "renewal",
  "change",
  "subscription",
  "promocode",
  "custom",
];

function StateBadge({ label }: { label: string }) {
  return (
    <span className="shrink-0 rounded-full border border-warning/30 bg-warning/10 px-1.5 py-px text-[9.5px] font-semibold uppercase tracking-wide text-warning">
      {label}
    </span>
  );
}

function WindowChip({
  window,
  label,
  isSelected,
  isUnreachable,
  isDirty,
  canDelete,
  onSelect,
  onDelete,
}: {
  window: DialogWindow;
  label: string;
  isSelected: boolean;
  isUnreachable: boolean;
  isDirty: boolean;
  canDelete: boolean;
  onSelect: () => void;
  onDelete: () => void;
}) {
  const { t } = useTranslation();
  return (
    <div
      className={`group flex items-center gap-1 rounded-full px-1 transition-colors ${
        isSelected ? "bg-accent" : "hover:bg-white/[0.04]"
      }`}
    >
      <button
        type="button"
        onClick={onSelect}
        title={window.key}
        className={`flex min-w-0 flex-1 cursor-pointer items-center gap-2 px-1.5 py-1.5 text-left text-[13px] ${
          isSelected ? "font-medium text-primary" : "text-foreground/80"
        } ${window.is_enabled ? "" : "opacity-55"}`}
      >
        <MessageSquare className={`size-3.5 shrink-0 ${isSelected ? "text-primary" : "text-muted-foreground"}`} />
        <span className="min-w-0 flex-1 truncate">
          {label.length > LABEL_MAX_LENGTH ? `${label.slice(0, LABEL_MAX_LENGTH)}…` : label}
        </span>
        {isDirty && <span className="size-1.5 shrink-0 rounded-full bg-warning" />}
        {!window.is_enabled && <StateBadge label={t("dialogs.windowList.disabledBadge")} />}
        {isUnreachable && <StateBadge label={t("dialogs.windowList.unlinkedBadge")} />}
      </button>
      {canDelete && window.kind === "custom" ? (
        <button
          type="button"
          onClick={onDelete}
          aria-label={t("dialogs.windowList.deleteWindow")}
          className="cursor-pointer px-1 text-[13px] text-muted-foreground opacity-0 transition-opacity hover:text-error group-hover:opacity-100"
        >
          ×
        </button>
      ) : null}
    </div>
  );
}

export function WindowSwitcher({
  windows,
  labelOf,
  unreachableKeys,
  dirtyKey,
  selectedKey,
  onSelect,
  canCreate,
  isLimitReached,
  canDelete,
  onCreate,
  onDelete,
}: WindowSwitcherProps) {
  const { t } = useTranslation();
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [titleText, setTitleText] = useState("");
  const [collapsedFlows, setCollapsedFlows] = useState<string[]>([]);

  const branches = FLOW_ORDER.map((flow) => ({
    flow,
    items: windows.filter((window) => window.flow === flow),
  })).filter((branch) => branch.items.length > 0);

  const toggleFlow = (flow: DialogFlow) =>
    setCollapsedFlows((current) =>
      current.includes(flow) ? current.filter((item) => item !== flow) : [...current, flow],
    );

  return (
    <div className="flex flex-col gap-0.5">
      {branches.map(({ flow, items }) => {
        const isCollapsed = collapsedFlows.includes(flow);
        return (
          <div key={flow}>
            <button
              type="button"
              onClick={() => toggleFlow(flow)}
              className="flex w-full cursor-pointer items-center gap-1 rounded-lg px-1.5 py-1.5 text-left text-[11px] uppercase tracking-wide text-muted-foreground transition-colors hover:bg-white/[0.06]"
            >
              <ChevronRight
                className={`size-3 shrink-0 transition-transform ${isCollapsed ? "" : "rotate-90"}`}
              />
              <span className="truncate">{t(`dialogs.windowList.flows.${flow}`)}</span>
              <span className="ml-auto text-[10.5px] tabular-nums opacity-70">{items.length}</span>
            </button>
            {!isCollapsed && (
              <div className="ml-[13px] flex flex-col gap-0.5 border-l border-white/[0.08] pl-1.5">
                {items.map((window) => (
                  <WindowChip
                    key={window.key}
                    window={window}
                    label={labelOf(window)}
                    isSelected={window.key === selectedKey}
                    isUnreachable={unreachableKeys.has(window.key)}
                    isDirty={window.key === dirtyKey}
                    canDelete={canDelete}
                    onSelect={() => onSelect(window.key)}
                    onDelete={() => setDeleteTarget(window.key)}
                  />
                ))}
              </div>
            )}
          </div>
        );
      })}
      {canCreate && (
        <button
          type="button"
          onClick={() => setIsCreateOpen(true)}
          className="mt-1 w-full cursor-pointer rounded-lg border border-dashed border-white/[0.12] px-2.5 py-1.5 text-left text-[12px] text-foreground/70 hover:bg-white/[0.06]"
        >
          {t("dialogs.windowList.addWindow")}
        </button>
      )}
      {isLimitReached && (
        <span className="mt-1 text-[11.5px] text-muted-foreground">
          {t("dialogs.windowList.limitReached")}
        </span>
      )}
      {isCreateOpen && (
        <ConfirmDialog
          title={t("dialogs.windowList.addWindow")}
          message={t("dialogs.windowList.addWindowMessage")}
          confirmLabel={t("dialogs.windowList.addWindowConfirm")}
          cancelLabel={t("dialogs.windowList.addWindowCancel")}
          onConfirm={() => {
            if (!titleText.trim()) return;
            onCreate(titleText.trim(), null);
            setIsCreateOpen(false);
            setTitleText("");
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
