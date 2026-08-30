import { createContext } from "react";

import type { CurrentUser } from "@entities/user/api";
import type { AsyncState } from "@shared/lib/use-async-resource";

export const CurrentUserContext = createContext<AsyncState<CurrentUser> | null>(null);
export const CurrentUserReloadContext = createContext<(() => void) | null>(null);
