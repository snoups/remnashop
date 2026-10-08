import { useEffect } from "react";

import type { AccessSettings } from "@entities/settings/api";

const listeners = new Set<(settings: AccessSettings) => void>();

// the header badge lives outside the Access tab and would otherwise show a stale mode
export function publishAccessSettings(settings: AccessSettings): void {
  listeners.forEach((listener) => listener(settings));
}

export function useOnAccessSettingsSaved(listener: (settings: AccessSettings) => void): void {
  useEffect(() => {
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  }, [listener]);
}
