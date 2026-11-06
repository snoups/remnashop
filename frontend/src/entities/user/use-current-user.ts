import { useContext, useMemo } from "react";

import type { CurrentUser } from "@entities/user/api";
import type { AsyncState } from "@shared/lib/use-async-resource";
import type { Permission } from "@shared/types/rbac";

import { CurrentUserContext, CurrentUserReloadContext } from "./context";

// stable identity, so callers can list the result as an effect dependency
const EMPTY_PERMISSIONS: Permission[] = [];

// writes the backend refuses on one's own account without STAFF_SELF_MANAGE
const OWN_ACCOUNT_WRITES: ReadonlySet<Permission> = new Set<Permission>([
  "SUBSCRIPTIONS_GRANT",
  "SUBSCRIPTIONS_UPDATE",
  "SUBSCRIPTIONS_DELETE",
  "SUBSCRIPTIONS_PLAN_CHANGE",
  "SUBSCRIPTIONS_STATUS_MANAGE",
  "SUBSCRIPTIONS_TRAFFIC_RESET",
  "SUBSCRIPTIONS_SQUADS_MANAGE",
  "SUBSCRIPTIONS_LINK_REISSUE",
  "SUBSCRIPTIONS_DEVICES_DELETE",
  "SUBSCRIPTIONS_DEVICES_DELETE_ALL",
  "SUBSCRIPTIONS_PULL_FROM_PANEL",
  "SUBSCRIPTIONS_PUSH_TO_PANEL",
  "REFERRALS_POINTS_MANAGE",
  "REFERRALS_BONUS_DAYS_MANAGE",
  "USERS_DISCOUNT_MANAGE",
]);

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

/** The current user's permissions over one account's subscriptions and balance. */
export function useAccountPermissions(userId: number): Permission[] {
  const state = useCurrentUser();
  const permissions = usePermissions();
  const isOwn = state.kind === "ready" && state.data.id === userId;
  return useMemo(
    () =>
      isOwn && !permissions.includes("STAFF_SELF_MANAGE")
        ? permissions.filter((permission) => !OWN_ACCOUNT_WRITES.has(permission))
        : permissions,
    [isOwn, permissions],
  );
}
