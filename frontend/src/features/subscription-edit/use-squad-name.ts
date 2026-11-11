import { listPanelSquads } from "@entities/subscriptions/api";
import { usePermissions } from "@entities/user/use-current-user";
import { useAsyncResource } from "@shared/lib/use-async-resource";

const shortUuid = (uuid: string) => `${uuid.slice(0, 8)}…`;

/** A squad's name from the panel; `unknown(uuid)` (the uuid's start by default) for one it no longer has, an
 *  unreachable panel or no right to list. */
export function useSquadName(unknown: (uuid: string) => string = shortUuid): (uuid: string) => string {
  const canView = usePermissions().includes("SUBSCRIPTIONS_PANEL_SQUADS_VIEW");
  const [squads] = useAsyncResource(
    (signal) => (canView ? listPanelSquads(signal) : Promise.resolve({ items: [], total: 0 })),
    { deps: [canView] },
  );
  return (uuid) =>
    (squads.kind === "ready" ? squads.data.items.find((squad) => squad.uuid === uuid)?.name : undefined) ??
    unknown(uuid);
}
