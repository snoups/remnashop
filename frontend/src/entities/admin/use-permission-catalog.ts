import { getPermissionCatalog, type PermissionCatalogEntry } from "@entities/admin/api";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import type { AsyncState } from "@shared/lib/use-async-resource";
import type { Permission } from "@shared/types/rbac";

// Catalog only changes with a backend deploy, so one fetch per page load is enough. Kept as data, not a
// promise, so a remounted picker renders ready on its first frame instead of flashing a spinner.
let cachedCatalog: PermissionCatalogEntry[] | null = null;
let inflightCatalog: Promise<PermissionCatalogEntry[]> | null = null;

function loadPermissionCatalog(): Promise<PermissionCatalogEntry[]> {
  if (cachedCatalog) return Promise.resolve(cachedCatalog);
  inflightCatalog ??= getPermissionCatalog()
    .then((entries) => {
      cachedCatalog = entries;
      return entries;
    })
    .finally(() => {
      inflightCatalog = null;
    });
  return inflightCatalog;
}

export function prefetchPermissionCatalog(): void {
  loadPermissionCatalog().catch(() => {});
}

export function usePermissionCatalog(): AsyncState<PermissionCatalogEntry[]> {
  const [state] = useAsyncResource(loadPermissionCatalog);
  return cachedCatalog ? { kind: "ready", data: cachedCatalog } : state;
}

/** `bot_settings` → `botSettings`, the `permissionCategories.*` locale key. */
export function resourceCategoryKey(resource: string): string {
  return resource.replace(/_([a-z])/g, (_, c: string) => c.toUpperCase());
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
