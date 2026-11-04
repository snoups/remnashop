import { createContext, useContext } from "react";

export interface RefreshSignal {
  token: number;
  refresh: () => void;
  /** when the page behind the refresh button last loaded; shown next to it */
  updatedAt: Date | null;
  setUpdatedAt: (date: Date | null) => void;
}

export const RefreshSignalContext = createContext<RefreshSignal>({
  token: 0,
  refresh: () => {},
  updatedAt: null,
  setUpdatedAt: () => {},
});

export const useRefreshSignal = (): RefreshSignal => useContext(RefreshSignalContext);
