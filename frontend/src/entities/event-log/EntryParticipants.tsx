import { useTranslation } from "react-i18next";

import type { EventLogEntry } from "@entities/event-log/api";
import type { UserSnapshot } from "@entities/event-log/describe-entry";
import {
  getInitiator,
  getMissingInitiatorKey,
  getUserSnapshot,
  PAYLOAD_TARGET_KEY,
  participantId,
  participantName,
} from "@entities/event-log/describe-entry";

/** A name with a mono "#id", as in the users list. */
function Participant({ user }: { user: UserSnapshot }) {
  const { t } = useTranslation();
  const id = participantId(user);
  return (
    <>
      {participantName(user, t)}
      {id !== undefined && <span className="ml-1.5 font-mono text-[12px] text-muted-foreground">#{id}</span>}
    </>
  );
}

/** Who did it, and to whom when the event has a target: "admin #1 → Ivan #42". */
export function EntryParticipants({ entry }: { entry: EventLogEntry }) {
  const { t } = useTranslation();
  const initiator = getInitiator(entry);
  const target = getUserSnapshot(entry, PAYLOAD_TARGET_KEY);
  return (
    <>
      {initiator ? <Participant user={initiator} /> : t(getMissingInitiatorKey(entry))}
      {target && (
        <>
          {" → "}
          <Participant user={target} />
        </>
      )}
    </>
  );
}
