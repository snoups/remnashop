import { ChevronRight, MessagesSquare, Plus } from "lucide-react";
import { motion } from "motion/react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import type { DialogFlow, DialogWindow } from "@entities/dialogs/api";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
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
  onCreate: (name: string) => void;
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
  bounceStrength,
  onSelect,
  onDelete,
}: {
  window: DialogWindow;
  label: string;
  isSelected: boolean;
  isUnreachable: boolean;
  isDirty: boolean;
  canDelete: boolean;
  bounceStrength: number;
  onSelect: () => void;
  onDelete: () => void;
}) {
  const { t } = useTranslation();
  return (
    <motion.div
      initial="rest"
      whileTap="tap"
      className="group relative isolate flex items-center gap-1 rounded-full px-1"
    >
      {/* Only the pill behind the row scales on tap, same split as TabBar. */}
      <motion.span
        aria-hidden
        variants={{ rest: { scale: 1 }, tap: { scale: 1 + 0.05 * bounceStrength } }}
        className={`absolute inset-0 rounded-full transition-colors ${
          isSelected ? "bg-accent" : "group-hover:bg-white/[0.04]"
        }`}
      />
      <button
        type="button"
        onClick={onSelect}
        className={`relative z-10 flex min-w-0 flex-1 cursor-pointer items-center gap-2 px-1.5 py-1.5 text-left text-[13px] ${
          isSelected ? "font-medium text-primary" : "text-foreground/80"
        } ${window.is_enabled ? "" : "opacity-55"}`}
      >
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
          className="relative z-10 cursor-pointer px-1 text-[13px] text-muted-foreground opacity-0 transition-opacity hover:text-error group-hover:opacity-100"
        >
          ×
        </button>
      ) : null}
    </motion.div>
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
  const bounceStrength = useBounceStrength();
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<DialogWindow | null>(null);
  const [name, setName] = useState("");
  // Only what somebody clicked is remembered; everything else follows the
  // selection, so the flow holding the open window is the one left expanded.
  const [toggledFlows, setToggledFlows] = useState<Record<string, boolean>>({});

  const branches = FLOW_ORDER.map((flow) => ({
    flow,
    items: windows.filter((window) => window.flow === flow),
  })).filter((branch) => branch.items.length > 0);

  const activeFlow = windows.find((window) => window.key === selectedKey)?.flow ?? null;
  const isFlowCollapsed = (flow: DialogFlow) => toggledFlows[flow] ?? flow !== activeFlow;

  const toggleFlow = (flow: DialogFlow) =>
    setToggledFlows((current) => ({ ...current, [flow]: !isFlowCollapsed(flow) }));

  return (
    <div className="flex flex-col gap-1.5">
      {branches.map(({ flow, items }) => {
        const isCollapsed = isFlowCollapsed(flow);
        return (
          <div key={flow}>
            <motion.button
              type="button"
              onClick={() => toggleFlow(flow)}
              initial="rest"
              whileTap="tap"
              className="group relative isolate flex w-full cursor-pointer items-center gap-1 rounded-full px-1.5 py-1.5 text-left text-[11px] uppercase leading-5 tracking-wide text-muted-foreground"
            >
              <motion.span
                aria-hidden
                variants={{ rest: { scale: 1 }, tap: { scale: 1 + 0.05 * bounceStrength } }}
                className="absolute inset-0 rounded-full transition-colors group-hover:bg-white/[0.06]"
              />
              <ChevronRight
                className={`relative z-10 size-3 shrink-0 transition-transform ${isCollapsed ? "" : "rotate-90"}`}
              />
              <span className="relative z-10 truncate">
                {t(`dialogs.windowList.flows.${flow}`)}
              </span>
              <span className="relative z-10 ml-auto text-[10.5px] tabular-nums opacity-70">
                {items.length}
              </span>
            </motion.button>
            {!isCollapsed && (
              <div className="ml-[13px] mt-1 flex flex-col gap-0.5 border-l border-white/[0.08] pl-1.5">
                {items.map((window) => (
                  <WindowChip
                    key={window.key}
                    window={window}
                    label={labelOf(window)}
                    isSelected={window.key === selectedKey}
                    isUnreachable={unreachableKeys.has(window.key)}
                    isDirty={window.key === dirtyKey}
                    canDelete={canDelete}
                    bounceStrength={bounceStrength}
                    onSelect={() => onSelect(window.key)}
                    onDelete={() => setDeleteTarget(window)}
                  />
                ))}
              </div>
            )}
          </div>
        );
      })}
      {canCreate && (
        <motion.button
          type="button"
          onClick={() => setIsCreateOpen(true)}
          {...bounceTap(bounceStrength)}
          className="mt-1 flex w-full cursor-pointer items-center justify-center gap-1.5 rounded-full border border-dashed border-white/[0.12] px-4 py-1.5 text-[13px] text-foreground/70 transition-colors hover:bg-white/[0.06]"
        >
          <Plus className="size-3.5" />
          {t("dialogs.windowList.addWindow")}
        </motion.button>
      )}
      {isLimitReached && (
        <span className="mt-1 text-[11.5px] text-muted-foreground">
          {t("dialogs.windowList.limitReached")}
        </span>
      )}
      {isCreateOpen && (
        <ConfirmDialog
          title={t("dialogs.windowList.addWindow")}
          icon={MessagesSquare}
          confirmLabel={t("dialogs.windowList.addWindowConfirm")}
          cancelLabel={t("dialogs.windowList.addWindowCancel")}
          onConfirm={() => {
            if (!name.trim()) return;
            onCreate(name.trim());
            setIsCreateOpen(false);
            setName("");
          }}
          onCancel={() => setIsCreateOpen(false)}
        >
          <input
            type="text"
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder={t("dialogs.windowList.addWindowTitlePlaceholder")}
            className="mb-2 w-full rounded-lg border border-border bg-input/60 px-2.5 py-1.5 text-[13px]"
          />
        </ConfirmDialog>
      )}
      {deleteTarget && (
        <ConfirmDialog
          title={t("dialogs.windowList.deleteWindow")}
          message={t("dialogs.windowList.deleteWindowConfirm", { name: labelOf(deleteTarget) })}
          confirmLabel={t("dialogs.windowList.deleteWindowConfirmButton")}
          cancelLabel={t("dialogs.windowList.deleteWindowCancelButton")}
          danger
          onConfirm={() => {
            onDelete(deleteTarget.key);
            setDeleteTarget(null);
          }}
          onCancel={() => setDeleteTarget(null)}
        />
      )}
    </div>
  );
}
