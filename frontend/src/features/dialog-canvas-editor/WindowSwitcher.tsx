import { EyeOff, Plus, Unlink } from "lucide-react";
import { motion } from "motion/react";
import { useId, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import type { DialogFlow, DialogWindow } from "@entities/dialogs/api";
import { CreateWindowDialog } from "@features/dialog-canvas-editor/CreateWindowDialog";
import { useHorizontalWheelScroll } from "@shared/lib/use-horizontal-wheel-scroll";
import { SegmentedPills } from "@shared/ui/SegmentedPills";

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
  /** resolves true once created; the dialog stays open on false */
  onCreate: (name: string) => Promise<boolean>;
  /** beside the flow pills, at the end of the line: the locale switch */
  aside?: ReactNode;
}

// custom windows are their own flow and sit last
const FLOW_ORDER: DialogFlow[] = ["menu", "purchase", "renewal", "change", "subscription", "promocode", "referrals", "custom"];

/** Two levels: the flows as pills, the open flow's windows as underline tabs under them. A window's
 *  state shows as an icon on its tab; the inspector spells it out. */
export function WindowSwitcher({
  windows,
  labelOf,
  unreachableKeys,
  dirtyKey,
  selectedKey,
  onSelect,
  canCreate,
  isLimitReached,
  onCreate,
  aside,
}: WindowSwitcherProps) {
  const { t } = useTranslation();
  const underlineId = useId();
  const wheelRef = useHorizontalWheelScroll<HTMLDivElement>();
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const selectedFlow = windows.find((window) => window.key === selectedKey)?.flow;
  // the custom flow is picked with no window in it yet, to add the first one
  const [emptyFlow, setEmptyFlow] = useState<DialogFlow | null>(null);
  const flow = emptyFlow ?? selectedFlow ?? "menu";
  const flows = FLOW_ORDER.filter((item) => windows.some((window) => window.flow === item) || (item === "custom" && canCreate));

  const pickFlow = (next: DialogFlow) => {
    const first = windows.find((window) => window.flow === next);
    if (first) {
      setEmptyFlow(null);
      onSelect(first.key);
    } else {
      setEmptyFlow(next);
    }
  };

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <SegmentedPills
          compact
          value={flow}
          onChange={pickFlow}
          options={flows.map((item) => ({ value: item, label: t(`dialogs.windowList.flows.${item}`) }))}
        />
        {aside}
      </div>
      <div ref={wheelRef} className="no-scrollbar flex gap-1 overflow-x-auto border-b border-white/[0.08] px-1">
        {windows
          .filter((window) => window.flow === flow)
          .map((window) => {
            const isActive = window.key === selectedKey;
            return (
              // no ripple: a tab strip, like PillTabs
              <button
                key={window.key}
                type="button"
                onClick={() => {
                  setEmptyFlow(null);
                  onSelect(window.key);
                }}
                className={`group relative flex h-11 shrink-0 cursor-pointer items-center gap-1.5 rounded-lg px-3 text-sm font-medium transition-colors ${
                  isActive ? "text-foreground" : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {/* hover previews the underline the tab gets once open */}
                {!isActive && (
                  <span className="absolute inset-x-3 -bottom-px h-0.5 rounded-full transition-colors group-hover:bg-white/20" />
                )}
                <span className={`${window.is_enabled ? "" : "line-through decoration-muted-foreground/60"}`}>
                  {labelOf(window)}
                </span>
                {!window.is_enabled && <EyeOff className="size-3.5 text-muted-foreground" />}
                {unreachableKeys.has(window.key) && <Unlink className="size-3.5 text-warning" />}
                {window.key === dirtyKey && <span className="size-1.5 rounded-full bg-warning" />}
                {isActive && (
                  <motion.span
                    layoutId={underlineId}
                    transition={{ type: "spring", stiffness: 500, damping: 40 }}
                    className="absolute inset-x-3 -bottom-px h-0.5 rounded-full bg-primary"
                  />
                )}
              </button>
            );
          })}
        {flow === "custom" &&
          (canCreate ? (
            <button
              type="button"
              onClick={() => setIsCreateOpen(true)}
              className="flex h-11 shrink-0 cursor-pointer items-center gap-1.5 rounded-lg px-3 text-sm text-muted-foreground transition-colors hover:text-primary"
            >
              <Plus className="size-3.5" />
              {t("dialogs.windowList.addWindow")}
            </button>
          ) : (
            isLimitReached && (
              <span className="flex h-11 shrink-0 items-center px-3 text-xs text-muted-foreground">
                {t("dialogs.windowList.limitReached")}
              </span>
            )
          ))}
      </div>
      {isCreateOpen && (
        <CreateWindowDialog
          onCreate={async (name) => {
            const created = await onCreate(name);
            if (created) setEmptyFlow(null);
            return created;
          }}
          onClose={() => setIsCreateOpen(false)}
        />
      )}
    </div>
  );
}
