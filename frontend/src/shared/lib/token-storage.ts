// In-memory only, not localStorage/sessionStorage -- an XSS payload that runs
// in this page can't read a token that isn't stored anywhere DOM-accessible.
// Lost on a hard reload by design; @shared/api/http's initializeAuth()
// re-derives it from the httponly refresh cookie on app boot.
let accessToken: string | null = null;

export function saveAccessToken(token: string): void {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

export function clearAccessToken(): void {
  accessToken = null;
}

// Reads the "sid" claim from the JWT payload, unverified -- for UI display
// only (highlighting the current device in a session list), never for
// authorization decisions.
export function getSessionId(): number | null {
  const token = getAccessToken();
  if (!token) return null;
  try {
    const base64 = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    const payload = JSON.parse(atob(base64)) as { sid?: number };
    return payload.sid ?? null;
  } catch {
    return null;
  }
}
