import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { SessionList } from "@entities/auth/SessionList";
import {
  type Session,
  listOwnSessions,
  listUserSessions,
  revokeOwnSession,
  revokeUserSession,
} from "@entities/auth/sessions";
import { disablePushOnSignOut } from "@entities/notifications/push-api";
import { getErrorMessage, logout } from "@shared/api/http";
import { clearAccessToken, getSessionId } from "@shared/lib/token-storage";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { ErrorState } from "@shared/ui/glass/EmptyState";
import { Spinner } from "@shared/ui/Spinner";

/** Sessions with revoke: the actor's own without `userId`, another account's with it. */
export function SessionsPanel({
  userId,
  version = 0,
  rowSize = "compact",
}: {
  userId?: number;
  /** bumped to reload in place */
  version?: number;
  rowSize?: "default" | "compact";
}) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const isOwn = userId === undefined;
  const currentSessionId = isOwn ? getSessionId() : null;
  const [state, reload] = useAsyncResource(
    (signal) => (isOwn ? listOwnSessions(signal) : listUserSessions(userId, signal)),
    { deps: [version], keepData: true },
  );
  const [pendingRevoke, setPendingRevoke] = useState<Session | null>(null);
  const isRevokingCurrent = pendingRevoke !== null && pendingRevoke.id === currentSessionId;

  const handleRevoke = async (sessionId: number) => {
    try {
      // before the revoke: unsubscribing needs this session
      if (sessionId === currentSessionId) await disablePushOnSignOut();
      await (isOwn ? revokeOwnSession(sessionId) : revokeUserSession(userId, sessionId));
      if (sessionId === currentSessionId) {
        if (!(await logout())) toast.error(t("auth.errors.logoutNotConfirmed"));
        clearAccessToken();
        navigate("/", { replace: true });
        return;
      }
      reload();
    } catch (err) {
      toast.error(getErrorMessage(err, t("sessions.revokeError")));
    }
  };

  return (
    <>
      {state.kind === "loading" && <Spinner size="card" />}
      {state.kind === "error" && <ErrorState text={t("common.loadError")} />}
      {state.kind === "ready" && (
        <SessionList sessions={state.data} currentSessionId={currentSessionId} onRequestRevoke={setPendingRevoke} size={rowSize} />
      )}

      {pendingRevoke && (
        <ConfirmDialog
          title={t("sessions.revokeTitle")}
          message={isRevokingCurrent ? t("sessions.revokeConfirmCurrent") : t("sessions.revokeConfirm")}
          confirmLabel={t("sessions.revoke")}
          cancelLabel={t("common.cancel")}
          danger
          portal={!isOwn || isRevokingCurrent}
          onConfirm={() => {
            void handleRevoke(pendingRevoke.id);
            setPendingRevoke(null);
          }}
          onCancel={() => setPendingRevoke(null)}
        />
      )}
    </>
  );
}
