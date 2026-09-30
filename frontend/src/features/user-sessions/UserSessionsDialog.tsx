import { MonitorSmartphone } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { SessionList } from "@entities/auth/SessionList";
import {
  type Session,
  listOwnSessions,
  listUserSessions,
  revokeOwnSession,
  revokeUserSession,
} from "@entities/auth/sessions";
import { useCurrentUser } from "@entities/user/use-current-user";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { Modal } from "@shared/ui/Modal";
import { Spinner } from "@shared/ui/Spinner";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { DialogHeader } from "@shared/ui/DialogHeader";

interface UserSessionsDialogProps {
  userId: number;
  userName: string;
  onClose: () => void;
}

export function UserSessionsDialog({ userId, userName, onClose }: UserSessionsDialogProps) {
  return (
    <Modal onClose={onClose} size="sm">
      <UserSessionsDialogBody userId={userId} userName={userName} />
    </Modal>
  );
}

function UserSessionsDialogBody({ userId, userName }: Pick<UserSessionsDialogProps, "userId" | "userName">) {
  const { t } = useTranslation();
  const currentUserState = useCurrentUser();
  // the per-user endpoints reject equal-role targets, which includes yourself
  const isSelf = currentUserState.kind === "ready" && currentUserState.data.id === userId;
  const [state, reload] = useAsyncResource((signal) =>
    isSelf ? listOwnSessions(signal) : listUserSessions(userId, signal),
  );
  const [pendingRevoke, setPendingRevoke] = useState<Session | null>(null);

  const handleRevoke = async (sessionId: number) => {
    try {
      await (isSelf ? revokeOwnSession(sessionId) : revokeUserSession(userId, sessionId));
      reload();
    } catch (err) {
      toast.error(getErrorMessage(err, t("sessions.revokeError")));
    }
  };

  return (
    <>
      <DialogHeader icon={MonitorSmartphone} title={t("sessions.title")} subtitle={userName} />

      <div className="px-5 py-4">
        {state.kind === "loading" && <Spinner size="card" />}
        {state.kind === "error" && <p className="text-sm text-error">{t("sessions.loadError")}</p>}
        {state.kind === "ready" && <SessionList sessions={state.data} onRequestRevoke={setPendingRevoke} />}
      </div>

      {pendingRevoke && (
        <ConfirmDialog
          title={t("sessions.revokeTitle")}
          message={t("sessions.revokeConfirm")}
          confirmLabel={t("sessions.revoke")}
          cancelLabel={t("sessions.cancel")}
          danger
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
