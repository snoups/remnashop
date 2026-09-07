import { ArrowLeft, MonitorSmartphone, X } from "lucide-react";
import { motion } from "motion/react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { SessionList } from "@entities/auth/SessionList";
import { type Session, listUserSessions, revokeUserSession } from "@entities/auth/sessions";
import { getErrorMessage } from "@shared/api/http";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { Modal, useModalClose } from "@shared/ui/Modal";
import { Spinner } from "@shared/ui/Spinner";

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
  const bounceStrength = useBounceStrength();
  const close = useModalClose();
  const [state, reload] = useAsyncResource((signal) => listUserSessions(userId, signal));
  const [pendingRevoke, setPendingRevoke] = useState<Session | null>(null);

  const handleRevoke = async (sessionId: number) => {
    try {
      await revokeUserSession(userId, sessionId);
      reload();
    } catch (err) {
      toast.error(getErrorMessage(err, t("sessions.revokeError")));
    }
  };

  return (
    <>
      <div className="flex items-center gap-2 border-b border-border px-5 py-4">
        {pendingRevoke && (
          <button
            type="button"
            onClick={() => setPendingRevoke(null)}
            aria-label={t("sessions.back")}
            className="flex size-8 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-white/[0.06] hover:text-foreground"
          >
            <ArrowLeft className="size-4" />
          </button>
        )}
        {!pendingRevoke && (
          <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] text-foreground backdrop-blur-md">
            <MonitorSmartphone className="size-4" />
          </div>
        )}
        <div className="min-w-0 flex-1">
          <h2 className="text-base font-bold text-foreground">
            {pendingRevoke ? t("sessions.revokeTitle") : t("sessions.title")}
          </h2>
          {!pendingRevoke && <p className="mt-0.5 text-[12px] text-muted-foreground">{userName}</p>}
        </div>
        <button
          type="button"
          onClick={close}
          aria-label={t("profile.edit.close")}
          className="flex size-8 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-white/[0.06] hover:text-foreground"
        >
          <X className="size-4" />
        </button>
      </div>

      <div className="px-5 py-4">
        {pendingRevoke ? (
          <div className="flex flex-col gap-4">
            <p className="text-[12.5px] text-muted-foreground">{t("sessions.revokeConfirm")}</p>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setPendingRevoke(null)}
                className="flex-1 rounded-full border border-border px-4 py-2 text-sm font-medium text-foreground/80 transition-colors hover:bg-white/5"
              >
                {t("sessions.cancel")}
              </button>
              <motion.button
                type="button"
                onClick={() => {
                  void handleRevoke(pendingRevoke.id);
                  setPendingRevoke(null);
                }}
                {...bounceTap(bounceStrength)}
                className="flex-1 rounded-full border border-error/30 bg-error/10 px-4 py-2 text-sm font-medium text-error transition-colors hover:bg-error/20"
              >
                {t("sessions.revoke")}
              </motion.button>
            </div>
          </div>
        ) : (
          <>
            {state.kind === "loading" && <Spinner />}
            {state.kind === "error" && <p className="text-sm text-error">{t("sessions.loadError")}</p>}
            {state.kind === "ready" && <SessionList sessions={state.data} onRequestRevoke={setPendingRevoke} />}
          </>
        )}
      </div>
    </>
  );
}
