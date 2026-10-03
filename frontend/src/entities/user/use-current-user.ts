import { useContext } from "react";

import type { CurrentUser } from "@entities/user/api";
import type { AsyncState } from "@shared/lib/use-async-resource";
import type { Permission } from "@shared/types/rbac";

import { CurrentUserContext, CurrentUserReloadContext } from "./context";

// stable identity, so callers can list the result as an effect dependency
const EMPTY_PERMISSIONS: Permission[] = [];

export function useCurrentUser(): AsyncState<CurrentUser> {
  const state = useContext(CurrentUserContext);
  if (state === null) {
    throw new Error("useCurrentUser must be used within a CurrentUserProvider");
  }
  return state;
}

export function useReloadCurrentUser(): () => void {
  const reload = useContext(CurrentUserReloadContext);
  if (reload === null) {
    throw new Error("useReloadCurrentUser must be used within a CurrentUserProvider");
  }
  return reload;
}

/** The current user's effective permissions; empty until /users/me has loaded. */
export function usePermissions(): Permission[] {
  const state = useCurrentUser();
  return state.kind === "ready" ? state.data.effective_permissions : EMPTY_PERMISSIONS;
}
