import { createContext, useContext } from "react";

export interface RefreshSignal {
  token: number;
  refresh: () => void;
}

export const RefreshSignalContext = createContext<RefreshSignal>({ token: 0, refresh: () => {} });

export const useRefreshSignal = (): RefreshSignal => useContext(RefreshSignalContext);
