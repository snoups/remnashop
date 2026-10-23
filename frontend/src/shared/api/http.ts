import type { ParseKeys } from "i18next";

import i18n from "@shared/i18n";
import { getDebugState } from "@shared/lib/debug-bar";
import { clearAccessToken, getAccessToken, saveAccessToken } from "@shared/lib/token-storage";

export const BASE_URL = "/api/v1";

export interface ListResponse<T> {
  items: T[];
  total: number;
}

// rejected: the refresh token is dead, the session is over. unavailable: the
// backend didn't answer (offline, restarting, proxy 5xx); the session may be
// fine, so the caller keeps the token and fails only this request.
type RefreshResult = { kind: "token"; token: string } | { kind: "rejected" } | { kind: "unavailable" };

let refreshPromise: Promise<RefreshResult> | null = null;

export function readCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

async function attemptRefresh(): Promise<RefreshResult> {
  const csrfToken = readCookie("csrf_token");
  if (!csrfToken) return { kind: "rejected" };

  let response: Response;
  try {
    response = await fetch(`${BASE_URL}/auth/refresh`, {
      method: "POST",
      headers: { "X-CSRF-Token": csrfToken },
    });
  } catch {
    return { kind: "unavailable" };
  }
  // 429: the refresh endpoint is rate-limited, which says nothing about the session
  if (response.status >= 500 || response.status === 429) return { kind: "unavailable" };
  if (!response.ok) return { kind: "rejected" };
  try {
    const data = (await response.json()) as { access_token: string };
    return { kind: "token", token: data.access_token };
  } catch {
    return { kind: "unavailable" };
  }
}

function refreshOnce(): Promise<RefreshResult> {
  if (!refreshPromise) {
    refreshPromise = attemptRefresh().finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

// The access token lives in memory only (token-storage.ts) and a reload loses
// it; call once at boot to get it back from the refresh cookie before the
// route guards look.
export async function initializeAuth(): Promise<void> {
  if (!readCookie("csrf_token")) return;
  const result = await refreshOnce();
  if (result.kind === "token") saveAccessToken(result.token);
}

/**
 * Whether the server confirmed the revoke. Callers clear local state either
 * way, but on false the refresh token still works server-side and the user
 * should be told so.
 */
export async function logout(): Promise<boolean> {
  const csrfToken = readCookie("csrf_token");
  try {
    const response = await fetch(`${BASE_URL}/auth/logout`, {
      method: "POST",
      headers: csrfToken ? { "X-CSRF-Token": csrfToken } : {},
    });
    return response.ok;
  } catch {
    return false;
  }
}

export class ApiError extends Error {
  status: number;
  // ErrorCode from the backend; translated under apiErrors.*
  code: string | null;

  constructor(status: number, message: string, code: string | null = null) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

// Thrown when the backend itself is unreachable: either `fetch` fails outright
// (DNS/connection refused/offline), or the dev/reverse proxy in front of the
// API answers on its own with 502/503/504 because the upstream is down --
// distinct from ApiError, where the API itself responded with an error status.
export class NetworkError extends Error {}

const GATEWAY_ERROR_STATUSES = new Set([502, 503, 504]);

const DEBUG_FAILURE_EXEMPT_PATH = "/users/me";

export function getErrorMessage(err: unknown, fallback: string): string {
  if (!(err instanceof ApiError)) return fallback;
  const key = `apiErrors.${err.code}`;
  return err.code && i18n.exists(key) ? i18n.t(key as ParseKeys) : err.message;
}

function extractErrorCode(body: unknown): string | null {
  if (body && typeof body === "object" && "code" in body) {
    const code = (body as { code: unknown }).code;
    if (typeof code === "string") return code;
  }
  return null;
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

// A single fetch attempt: a connection failure becomes NetworkError, so neither
// the initial request nor the post-refresh retry can leak a raw TypeError.
async function sendRequest(path: string, init: RequestInit | undefined, bearer: string | null): Promise<Response> {
  const { apiFailure, latency } = getDebugState();
  if (latency) await new Promise((resolve) => setTimeout(resolve, latency));
  // /users/me is spared: its failure swaps the whole dashboard for an error screen
  if (path !== DEBUG_FAILURE_EXEMPT_PATH) {
    if (apiFailure === "network") throw new NetworkError("Forced failure (debug bar)");
    if (apiFailure === "server") throw new ApiError(500, "Forced failure (debug bar)");
  }

  const headers = new Headers(init?.headers);
  if (bearer) headers.set("Authorization", `Bearer ${bearer}`);

  try {
    return await fetch(`${BASE_URL}${path}`, { ...init, headers });
  } catch (err) {
    // A caller aborting via AbortSignal must propagate as-is, not surface as
    // a "backend unreachable" toast.
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    throw new NetworkError("Network request failed");
  }
}

function endSession(): void {
  clearAccessToken();
  window.location.href = "/";
}

// Every API call, JSON or binary, goes through here: a 401 on a live token
// refreshes it once and retries; only a refused refresh ends the session.
async function authorizedFetch(path: string, init?: RequestInit): Promise<Response> {
  const token = getAccessToken();
  const response = await sendRequest(path, init, token);
  if (response.status !== 401 || !token) return response;

  const refreshed = await refreshOnce();
  if (refreshed.kind === "unavailable") throw new NetworkError("Session refresh failed");
  if (refreshed.kind === "rejected") {
    endSession();
    return response;
  }
  saveAccessToken(refreshed.token);
  const retry = await sendRequest(path, init, refreshed.token);
  if (retry.status === 401) endSession();
  return retry;
}

function readBody(response: Response): Promise<unknown> {
  return response.json().catch(() => null);
}

// a proxy answering for a dead upstream has no error code; the API's own 502/503 does
function errorFor(response: Response, body: unknown): Error {
  if (GATEWAY_ERROR_STATUSES.has(response.status) && extractErrorCode(body) === null) {
    return new NetworkError("Backend unreachable");
  }
  return new ApiError(response.status, extractErrorMessage(body), extractErrorCode(body));
}

async function request<TResponse>(path: string, init?: RequestInit): Promise<TResponse> {
  const response = await authorizedFetch(path, init);
  const body = await readBody(response);
  if (!response.ok) throw errorFor(response, body);
  return body as TResponse;
}

/** The raw response of a GET whose body isn't JSON (an image, a file); same refresh and errors as apiGet. */
export async function apiGetRaw(path: string, signal?: AbortSignal): Promise<Response> {
  const response = await authorizedFetch(path, { signal });
  if (!response.ok) throw errorFor(response, await readBody(response));
  return response;
}

export function apiGet<TResponse>(path: string, signal?: AbortSignal): Promise<TResponse> {
  return request<TResponse>(path, { signal });
}

export function apiPost<TResponse, TBody>(
  path: string,
  body: TBody,
  signal?: AbortSignal,
): Promise<TResponse> {
  return request<TResponse>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
}

export function apiPut<TResponse, TBody>(
  path: string,
  body: TBody,
  signal?: AbortSignal,
): Promise<TResponse> {
  return request<TResponse>(path, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
}

export function apiPatch<TResponse, TBody>(
  path: string,
  body: TBody,
  signal?: AbortSignal,
): Promise<TResponse> {
  return request<TResponse>(path, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
}

export function apiDelete<TResponse, TBody = never>(
  path: string,
  body?: TBody,
  signal?: AbortSignal,
): Promise<TResponse> {
  if (body === undefined) return request<TResponse>(path, { method: "DELETE", signal });
  return request<TResponse>(path, {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
}

export function apiUpload<TResponse>(
  path: string,
  body: FormData | Blob,
  method: "PUT" | "POST" = "PUT",
): Promise<TResponse> {
  // a Blob body carries its own type as Content-Type
  return request<TResponse>(path, { method, body });
}
