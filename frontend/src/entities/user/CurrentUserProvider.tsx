import type { ReactNode } from "react";

import { getCurrentUser } from "@entities/user/api";
import { useAsyncResource } from "@shared/lib/use-async-resource";

import { CurrentUserContext, CurrentUserReloadContext } from "./context";

export function CurrentUserProvider({ children }: { children: ReactNode }) {
  const [state, reload] = useAsyncResource(getCurrentUser);

  return (
    <CurrentUserContext.Provider value={state}>
      <CurrentUserReloadContext.Provider value={reload}>
        {children}
      </CurrentUserReloadContext.Provider>
    </CurrentUserContext.Provider>
  );
}
