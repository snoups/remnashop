import type { ReactNode } from "react";

import { getCurrentUser } from "@entities/user/api";
import { useDebugState } from "@shared/lib/debug-bar";
import { useAsyncResource } from "@shared/lib/use-async-resource";

import { CurrentUserContext, CurrentUserReloadContext } from "./context";

export function CurrentUserProvider({ children }: { children: ReactNode }) {
  const [state, reload] = useAsyncResource(getCurrentUser);
  const { noPermissions } = useDebugState();

  // Debug-bar switch: the frontend gating only (Sidebar, page guards) -- the
  // API still answers whatever the real account may see.
  const visible =
    noPermissions && state.kind === "ready"
      ? { ...state, data: { ...state.data, effective_permissions: [] } }
      : state;

  return (
    <CurrentUserContext.Provider value={visible}>
      <CurrentUserReloadContext.Provider value={reload}>
        {children}
      </CurrentUserReloadContext.Provider>
    </CurrentUserContext.Provider>
  );
}
