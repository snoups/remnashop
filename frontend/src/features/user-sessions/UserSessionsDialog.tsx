import { ArrowLeft, MonitorSmartphone, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { SessionList } from "@entities/auth/SessionList";
import { type Session, listUserSessions, revokeUserSession } from "@entities/auth/sessions";
import { getErrorMessage } from "@shared/api/http";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { DialogPortal } from "@shared/ui/DialogPortal";

interface UserSessionsDialogProps {
  userId: number;
  userName: string;
  onClose: () => void;
}

export function UserSessionsDialog({ userId, userName, onClose }: UserSessionsDialogProps) {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const [state, reload] = useAsyncResource(() => listUserSessions(userId));
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
    <DialogPortal>
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.15, ease: "easeOut" }}
        className="fixed inset-0 z-40 flex items-center justify-center bg-black/55 backdrop-blur-3xl p-4"
      >
        <button
          type="button"
          aria-hidden
          tabIndex={-1}
          className="absolute inset-0 cursor-default"
          onClick={onClose}
        />

        <motion.div
          initial={{ opacity: 0, scale: 0.94, y: 8 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.94, y: 8 }}
          transition={{ duration: 0.18, ease: "easeOut" }}
          className="relative z-50 w-full max-w-sm rounded-dialog border border-white/[0.14] bg-popover/60 shadow-[0_24px_48px_-20px_rgba(4,8,20,0.6),inset_0_1px_0_rgba(232,236,251,0.16)] backdrop-blur-2xl backdrop-saturate-150"
        >
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
              onClick={onClose}
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
                {state.kind === "loading" && <p className="text-sm text-muted-foreground">{t("sessions.loading")}</p>}
                {state.kind === "error" && <p className="text-sm text-error">{t("sessions.loadError")}</p>}
                {state.kind === "ready" && (
                  <SessionList sessions={state.data} onRequestRevoke={setPendingRevoke} />
                )}
              </>
            )}
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
    </DialogPortal>
  );
}
