import { apiDelete, apiGet, apiPost } from "@shared/api/http";
import type { ListResponse } from "@shared/api/http";

import type { AuthResult } from "./api";

export type OAuthProvider = "github" | "telegram" | "oidc";

export const OAUTH_PROVIDERS: OAuthProvider[] = ["github", "telegram", "oidc"];

export interface OAuthAuthorizeResult {
  authorization_url: string;
}

export interface OAuthCallbackPayload {
  code: string;
  state: string;
}

export interface OAuthIdentity {
  provider: string;
  external_login: string | null;
}

export function getOAuthLoginAuthorizeUrl(provider: OAuthProvider): Promise<OAuthAuthorizeResult> {
  return apiGet<OAuthAuthorizeResult>(`/auth/oauth/${provider}/authorize`);
}

export function oauthLoginCallback(
  provider: OAuthProvider,
  payload: OAuthCallbackPayload,
): Promise<AuthResult> {
  return apiPost<AuthResult, OAuthCallbackPayload>(`/auth/oauth/${provider}/callback`, payload);
}

export function listConnectedAccounts(signal?: AbortSignal): Promise<OAuthIdentity[]> {
  return apiGet<ListResponse<OAuthIdentity>>("/auth/oauth", signal).then((response) => response.items);
}

export function getOAuthConnectAuthorizeUrl(
  provider: OAuthProvider,
): Promise<OAuthAuthorizeResult> {
  return apiGet<OAuthAuthorizeResult>(`/auth/oauth/${provider}/connect/authorize`);
}

export function oauthConnectCallback(
  provider: OAuthProvider,
  payload: OAuthCallbackPayload,
): Promise<OAuthIdentity> {
  return apiPost<OAuthIdentity, OAuthCallbackPayload>(
    `/auth/oauth/${provider}/connect/callback`,
    payload,
  );
}

export function disconnectOAuth(provider: OAuthProvider): Promise<void> {
  return apiDelete<void>(`/auth/oauth/${provider}`);
}
