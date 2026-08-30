import { apiGet } from "@shared/api/http";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import type { AsyncState } from "@shared/lib/use-async-resource";
import type { Permission } from "@shared/types/rbac";

export interface PermissionCatalogEntry {
  permission: Permission;
  resource: string;
  kind: "read" | "write";
}

interface PermissionCatalogResponse {
  entries: PermissionCatalogEntry[];
}

export function getPermissionCatalog(): Promise<PermissionCatalogEntry[]> {
  return apiGet<PermissionCatalogResponse>("/permissions/catalog").then((response) => response.entries);
}

export function usePermissionCatalog(): AsyncState<PermissionCatalogEntry[]> {
  const [state] = useAsyncResource(getPermissionCatalog);
  return state;
}

export interface PermissionCategoryGroup {
  resource: string;
  read: Permission[];
  write: Permission[];
}

export function groupCatalogByResource(entries: PermissionCatalogEntry[]): PermissionCategoryGroup[] {
  const byResource = new Map<string, PermissionCategoryGroup>();

  for (const entry of entries) {
    let group = byResource.get(entry.resource);
    if (!group) {
      group = { resource: entry.resource, read: [], write: [] };
      byResource.set(entry.resource, group);
    }
    if (entry.kind === "read") {
      group.read.push(entry.permission);
    } else {
      group.write.push(entry.permission);
    }
  }

  return Array.from(byResource.values());
}
