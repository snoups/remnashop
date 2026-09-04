import { getPermissionCatalog, type PermissionCatalogEntry } from "@entities/admin/api";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import type { AsyncState } from "@shared/lib/use-async-resource";
import type { Permission } from "@shared/types/rbac";

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
