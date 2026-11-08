import type { MissingSquad, SquadReplacements } from "@entities/subscriptions/api";

/** Every squad dropped: what a push does when the admin picks nothing. */
export function dropAllSquads(missing: MissingSquad[]): SquadReplacements {
  return Object.fromEntries(missing.map((squad) => [squad.uuid, null]));
}
