import { useContext } from "react";

import type { CurrentUser } from "@entities/user/api";
import type { AsyncState } from "@shared/lib/use-async-resource";

import { CurrentUserContext, CurrentUserReloadContext } from "./context";

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
