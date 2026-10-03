import { resourceCategoryKey } from "@entities/admin/use-permission-catalog";
import type { PermissionCatalogEntry } from "@entities/admin/api";
import type { TFunction } from "i18next";
import type { Permission } from "@shared/types/rbac";

export const SCOPE_WILDCARD = "*";

/**
 * Remnawave-style scopes: a fully selected resource (or one kind of it) becomes
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

export function tokenScopeLabel(scope: string, t: TFunction): string {
  const [resource, action] = scope.split(":");
  if (action === undefined) return t(`permissions.${scope}`);
  const category = t(`permissionCategories.${resourceCategoryKey(resource)}`);
  return action === SCOPE_WILDCARD ? category : `${category} · ${t(`permissionPicker.${action}`)}`;
}
