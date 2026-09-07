import { LaptopMinimal } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { SessionList } from "@entities/auth/SessionList";
import { type Session, listOwnSessions, revokeOwnSession } from "@entities/auth/sessions";
import { getErrorMessage, logout } from "@shared/api/http";
import { clearAccessToken, getSessionId } from "@shared/lib/token-storage";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { Spinner } from "@shared/ui/Spinner";

export function SessionsForm() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [state, reload] = useAsyncResource(listOwnSessions);
  const currentSessionId = getSessionId();
  const [pendingRevoke, setPendingRevoke] = useState<Session | null>(null);

  const handleRevoke = async (sessionId: number) => {
    try {
      await revokeOwnSession(sessionId);
      if (sessionId === currentSessionId) {
        await logout();
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
    <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-5">
      <div className="flex items-center gap-2.5">
        <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] text-foreground backdrop-blur-md">
          <LaptopMinimal className="size-4" />
        </div>
        <div>
          <h2 className="text-sm font-bold text-foreground">{t("sessions.title")}</h2>
          <p className="text-[12.5px] text-muted-foreground">{t("sessions.description")}</p>
        </div>
      </div>

      <div className="mt-3">
        {state.kind === "loading" && <Spinner />}
        {state.kind === "error" && <p className="text-sm text-error">{t("sessions.loadError")}</p>}
        {state.kind === "ready" && (
          <SessionList
            sessions={state.data}
            currentSessionId={currentSessionId}
            onRequestRevoke={setPendingRevoke}
          />
        )}
      </div>

      {pendingRevoke && (
        <ConfirmDialog
          title={t("sessions.revokeTitle")}
          message={
            pendingRevoke.id === currentSessionId
              ? t("sessions.revokeConfirmCurrent")
              : t("sessions.revokeConfirm")
          }
          confirmLabel={t("sessions.revoke")}
          cancelLabel={t("sessions.cancel")}
          danger
          portal={pendingRevoke.id === currentSessionId}
          onConfirm={() => {
            void handleRevoke(pendingRevoke.id);
            setPendingRevoke(null);
          }}
          onCancel={() => setPendingRevoke(null)}
        />
      )}
    </div>
  );
}
