import { readStorage, removeStorage, writeStorage } from "@shared/lib/safe-storage";

const STORAGE_KEY = "oauth_flow";

export type OAuthFlowPurpose = "login" | "connect";

export function setOAuthFlow(purpose: OAuthFlowPurpose): void {
  writeStorage(STORAGE_KEY, JSON.stringify({ purpose }), "session");
}

export function consumeOAuthFlow(): { purpose: OAuthFlowPurpose } | null {
  const raw = readStorage(STORAGE_KEY, "session");
  removeStorage(STORAGE_KEY, "session");
  if (!raw) return null;
  try {
    return JSON.parse(raw) as { purpose: OAuthFlowPurpose };
  } catch {
    return null;
  }
}
