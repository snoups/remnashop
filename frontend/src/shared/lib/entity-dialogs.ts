import { type RefObject, createContext, useContext, useEffect, useMemo, useRef } from "react";

import { ParentPanelContext } from "@shared/ui/modal-hooks";

export type EntityKind = "user" | "order" | "subscription" | "promocode" | "plan";

export interface EntityDialogRequest {
  kind: EntityKind;
  id: number;
  /** the entity itself when the caller already has it; fetched by id otherwise */
  data?: unknown;
  /** initial tab, for dialogs that have tabs */
  tab?: string;
  /** after a save or delete from inside the dialog */
  onChanged?: () => void;
  /** the dialog this one was opened from, so it nests there instead of stacking a second backdrop */
  parentPanel?: RefObject<HTMLDivElement | null> | null;
}

type OpenOptions = Omit<EntityDialogRequest, "kind" | "id" | "parentPanel">;

// Lets any slice open an entity's dialog on top of the current page without
// importing that dialog; the host that renders them lives in widgets.
export const EntityDialogContext = createContext<((request: EntityDialogRequest) => void) | null>(null);

export function useOpenEntity() {
  const host = useContext(EntityDialogContext);
  const parentPanel = useContext(ParentPanelContext);
  if (host === null) throw new Error("useOpenEntity must be used within an EntityDialogHost");
  return useMemo(() => {
    const open = (kind: EntityKind, id: number, options?: OpenOptions) => host({ kind, id, parentPanel, ...options });
    return {
      openUser: (id: number, options?: OpenOptions) => open("user", id, options),
      openOrder: (id: number, options?: OpenOptions) => open("order", id, options),
      openSubscription: (id: number, options?: OpenOptions) => open("subscription", id, options),
      openPromocode: (id: number, options?: OpenOptions) => open("promocode", id, options),
      openPlan: (id: number, options?: OpenOptions) => open("plan", id, options),
    };
  }, [host, parentPanel]);
}

const changeListeners = new Map<EntityKind, Set<() => void>>();

/** A dialog opened through the host saved or deleted an entity of this kind. */
export function notifyEntityChanged(kind: EntityKind): void {
  changeListeners.get(kind)?.forEach((listener) => listener());
}

/** Runs `onChange` when a host dialog changes an entity of this kind, so a page can refetch. */
export function useEntityChanged(kind: EntityKind, onChange: () => void): void {
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;
  useEffect(() => {
    const listener = () => onChangeRef.current();
    const listeners = changeListeners.get(kind) ?? new Set();
    listeners.add(listener);
    changeListeners.set(kind, listeners);
    return () => {
      listeners.delete(listener);
    };
  }, [kind]);
}
