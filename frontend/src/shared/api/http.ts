import { clearAccessToken, getAccessToken, saveAccessToken } from "@shared/lib/token-storage";

export const BASE_URL = "/api/v1";

let refreshPromise: Promise<string | null> | null = null;

export function readCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

async function attemptRefresh(): Promise<string | null> {
  const csrfToken = readCookie("csrf_token");
  if (!csrfToken) return null;

  try {
    const response = await fetch(`${BASE_URL}/auth/refresh`, {
      method: "POST",
      headers: { "X-CSRF-Token": csrfToken },
    });
    if (!response.ok) return null;
    const data = (await response.json()) as { access_token: string };
    return data.access_token;
  } catch {
    return null;
  }
}

function refreshOnce(): Promise<string | null> {
  if (!refreshPromise) {
    refreshPromise = attemptRefresh().finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

// The access token lives in memory only (see token-storage.ts), so a hard
// reload loses it -- call once at app boot to re-derive it from the
// httponly refresh cookie before route guards check for a token.
export async function initializeAuth(): Promise<void> {
  if (!readCookie("csrf_token")) return;
  const token = await refreshOnce();
  if (token) saveAccessToken(token);
}

export async function logout(): Promise<void> {
  const csrfToken = readCookie("csrf_token");
  try {
    await fetch(`${BASE_URL}/auth/logout`, {
      method: "POST",
      headers: csrfToken ? { "X-CSRF-Token": csrfToken } : {},
    });
  } catch {
    // best-effort -- local logout must proceed either way
  }
}

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

// Thrown when the backend itself is unreachable: either `fetch` fails outright
// (DNS/connection refused/offline), or the dev/reverse proxy in front of the
// API answers on its own with 502/503/504 because the upstream is down --
// distinct from ApiError, where the API itself responded with an error status.
export class NetworkError extends Error {}

const GATEWAY_ERROR_STATUSES = new Set([502, 503, 504]);

export function getErrorMessage(err: unknown, fallback: string): string {
  return err instanceof ApiError ? err.message : fallback;
}

function extractErrorMessage(body: unknown): string {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;

    if (typeof detail === "string") return detail;

    if (Array.isArray(detail)) {
      return detail
        .map((item) =>
          item && typeof item === "object" && "msg" in item
            ? String((item as { msg: unknown }).msg)
            : String(item),
        )
        .join("; ");
    }
  }

  return "Request failed";
}

async function request<TResponse>(path: string, init?: RequestInit): Promise<TResponse> {
  const token = getAccessToken();
  const headers = new Headers(init?.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);

  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, { ...init, headers });
  } catch {
    throw new NetworkError("Network request failed");
  }

  if (GATEWAY_ERROR_STATUSES.has(response.status)) {
    throw new NetworkError("Backend unreachable");
  }

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    if (response.status === 401 && token) {
      const newAccessToken = await refreshOnce();
      if (newAccessToken) {
        saveAccessToken(newAccessToken);
        const retryHeaders = new Headers(init?.headers);
        retryHeaders.set("Authorization", `Bearer ${newAccessToken}`);
        const retryResponse = await fetch(`${BASE_URL}${path}`, { ...init, headers: retryHeaders });
        const retryData = await retryResponse.json().catch(() => null);
        if (!retryResponse.ok) {
          if (retryResponse.status === 401) {
            clearAccessToken();
            window.location.href = "/";
          }
          throw new ApiError(retryResponse.status, extractErrorMessage(retryData));
        }
        return retryData as TResponse;
      }

      clearAccessToken();
      window.location.href = "/";
    }
    throw new ApiError(response.status, extractErrorMessage(data));
  }

  return data as TResponse;
}

export function apiGet<TResponse>(path: string): Promise<TResponse> {
  return request<TResponse>(path);
}

export function apiPost<TResponse, TBody>(path: string, body: TBody): Promise<TResponse> {
  return request<TResponse>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function apiPut<TResponse, TBody>(path: string, body: TBody): Promise<TResponse> {
  return request<TResponse>(path, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function apiPatch<TResponse, TBody>(path: string, body: TBody): Promise<TResponse> {
  return request<TResponse>(path, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function apiDelete<TResponse>(path: string): Promise<TResponse> {
  return request<TResponse>(path, { method: "DELETE" });
}

export function apiUpload<TResponse>(path: string, formData: FormData): Promise<TResponse> {
  return request<TResponse>(path, { method: "POST", body: formData });
}
