// In memory only, out of an XSS payload's reach. A reload loses it, and
// initializeAuth() (@shared/api/http) gets it back from the refresh cookie.
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

// The unverified "sid" claim, for marking the current device in a session
// list only; never for authorization.
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
