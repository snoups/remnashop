const STORAGE_KEY = "oauth_flow";

export type OAuthFlowPurpose = "login" | "connect";

export function setOAuthFlow(purpose: OAuthFlowPurpose): void {
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ purpose }));
}

export function consumeOAuthFlow(): { purpose: OAuthFlowPurpose } | null {
  const raw = sessionStorage.getItem(STORAGE_KEY);
  sessionStorage.removeItem(STORAGE_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as { purpose: OAuthFlowPurpose };
  } catch {
    return null;
  }
}
