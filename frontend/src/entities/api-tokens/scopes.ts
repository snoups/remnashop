import { resourceCategoryKey } from "@entities/admin/use-permission-catalog";
import type { PermissionCatalogEntry } from "@entities/admin/api";
import type { ParseKeys, TFunction } from "i18next";
import type { Permission } from "@shared/types/rbac";

const SCOPE_WILDCARD = "*";

/**
 * A fully selected resource (or one kind of it) becomes
 * `<resource>:*` / `<resource>:read|write` and so also covers permissions added to
 * it in later releases; a partial pick stays a list of single permissions.
 */
export function toTokenScopes(selected: Set<Permission>, catalog: PermissionCatalogEntry[]): string[] {
  const grantable = catalog.filter((entry) => entry.token_grantable);
  if (grantable.every((entry) => selected.has(entry.permission))) return [SCOPE_WILDCARD];

  const scopes: string[] = [];
  const resources = new Set(grantable.map((entry) => entry.resource));
  for (const resource of resources) {
    const entries = grantable.filter((entry) => entry.resource === resource);
    if (entries.every((entry) => selected.has(entry.permission))) {
      scopes.push(`${resource}:*`);
      continue;
    }
    for (const kind of ["read", "write"] as const) {
      const ofKind = entries.filter((entry) => entry.kind === kind);
      if (ofKind.length > 0 && ofKind.every((entry) => selected.has(entry.permission))) {
        scopes.push(`${resource}:${kind}`);
      } else {
        scopes.push(...ofKind.filter((entry) => selected.has(entry.permission)).map((entry) => entry.permission));
      }
    }
  }
  return scopes;
}

// what an external marketing page needs to render plans and prices
export const LANDING_PERMISSIONS: readonly Permission[] = ["PLANS_VIEW", "ADDONS_VIEW", "PRICING_VIEW"];

export type TokenPreset = "fullAccess" | "landing" | "readOnly";

function scopeEntries(scope: string, grantable: PermissionCatalogEntry[]): PermissionCatalogEntry[] {
  if (scope === SCOPE_WILDCARD) return grantable;
  const [resource, action] = scope.split(":");
  if (action === undefined) return grantable.filter((entry) => entry.permission === scope);
  return grantable.filter(
    (entry) => entry.resource === resource && (action === SCOPE_WILDCARD || entry.kind === action),
  );
}

/** The preset a token's scopes amount to; null for any other set, and for landing/read-only until the catalog loads. */
export function tokenPreset(scopes: string[], catalog: PermissionCatalogEntry[] | null): TokenPreset | null {
  if (scopes.includes(SCOPE_WILDCARD)) return "fullAccess";
  if (catalog === null) return null;
  const grantable = catalog.filter((entry) => entry.token_grantable);
  const entries = scopes.flatMap((scope) => scopeEntries(scope, grantable));
  const permissions = new Set(entries.map((entry) => entry.permission));
  if (permissions.size === 0) return null;
  if (permissions.size === LANDING_PERMISSIONS.length && LANDING_PERMISSIONS.every((key) => permissions.has(key))) {
    return "landing";
  }
  return entries.every((entry) => entry.kind === "read") ? "readOnly" : null;
}

/** The scopes to list one by one: a full-access token's `*` becomes every resource it reaches. */
export function listedTokenScopes(scopes: string[], catalog: PermissionCatalogEntry[] | null): string[] {
  if (!scopes.includes(SCOPE_WILDCARD) || catalog === null) return scopes;
  const resources = new Set(catalog.filter((entry) => entry.token_grantable).map((entry) => entry.resource));
  return [...resources].map((resource) => `${resource}:${SCOPE_WILDCARD}`);
}

export function tokenScopeLabel(scope: string, t: TFunction): string {
  const [resource, action] = scope.split(":");
  if (action === undefined) return t(`permissions.${scope}` as ParseKeys);
  const category = t(`permissionCategories.${resourceCategoryKey(resource)}` as ParseKeys);
  return action === SCOPE_WILDCARD ? category : `${category} · ${t(`permissionPicker.${action}` as ParseKeys)}`;
}
