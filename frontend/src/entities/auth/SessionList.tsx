import { MonitorSmartphone, Trash2 } from "lucide-react";
import { motion } from "motion/react";
import { useTranslation } from "react-i18next";

import type { Session } from "@entities/auth/sessions";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { parseUserAgent } from "@shared/lib/parse-user-agent";

interface SessionListProps {
  sessions: Session[];
  currentSessionId?: number | null;
  onRequestRevoke: (session: Session) => void;
}

export function SessionList({ sessions, currentSessionId, onRequestRevoke }: SessionListProps) {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();

  if (sessions.length === 0) {
    return <p className="text-sm text-muted-foreground">{t("sessions.empty")}</p>;
  }

  return (
    <div className="flex flex-col">
      {sessions.map((session) => {
        const { browser, os } = parseUserAgent(session.user_agent);
        const isCurrent = session.id === currentSessionId;
        return (
          <motion.button
            key={session.id}
            type="button"
            onClick={() => onRequestRevoke(session)}
            {...bounceTap(bounceStrength)}
            aria-label={t("sessions.revoke")}
            title={t("sessions.revoke")}
            className="group flex w-full items-center justify-between gap-3 rounded-full px-[12.5px] py-2.5 text-left transition-colors hover:bg-white/[0.04]"
          >
            <div className="flex items-center gap-3">
              <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-white/[0.06] text-foreground">
                <MonitorSmartphone className="size-4" />
              </div>
              <div>
                <p className="flex items-center gap-2 text-[13px] font-medium text-foreground">
                  {browser} · {os}
                  {isCurrent && (
                    <span className="rounded-full bg-accent px-2 py-0.5 text-[10.5px] font-semibold uppercase tracking-wide text-primary">
                      {t("sessions.thisDevice")}
                    </span>
                  )}
                </p>
                <p className="text-[12px] text-muted-foreground">
                  {session.ip_address} · {t("sessions.lastUsed", { date: new Date(session.last_used_at).toLocaleString() })}
                </p>
              </div>
            </div>
            <span className="flex size-8 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-colors group-hover:bg-error/10 group-hover:text-error">
              <Trash2 className="size-4" />
            </span>
          </motion.button>
        );
      })}
    </div>
  );
}
