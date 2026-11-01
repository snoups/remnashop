import { MonitorSmartphone, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";

import { formatDateTime } from "@shared/lib/relative-time";
import type { Session } from "@entities/auth/sessions";
import { parseUserAgent } from "@shared/lib/parse-user-agent";
import { EmptyState } from "@shared/ui/EmptyState";
import { Badge } from "@shared/ui/Badge";
import { Pressable } from "@shared/ui/Pressable";

interface SessionListProps {
  sessions: Session[];
  currentSessionId?: number | null;
  onRequestRevoke: (session: Session) => void;
}

export function SessionList({ sessions, currentSessionId, onRequestRevoke }: SessionListProps) {
  const { t, i18n } = useTranslation();

  if (sessions.length === 0) {
    return (
      <EmptyState text={t("sessions.empty")} />
    );
  }

  return (
    <div className="flex flex-col divide-y divide-border/50">
      {sessions.map((session) => {
        const { browser, os } = parseUserAgent(session.user_agent);
        const isCurrent = session.id === currentSessionId;
        return (
          <Pressable
            key={session.id}
            type="button"
            onClick={() => onRequestRevoke(session)}
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
                    <Badge tone="accent">
                      {t("sessions.thisDevice")}
                    </Badge>
                  )}
                </p>
                <p className="text-[12px] text-muted-foreground">
                  {session.ip_address} · {t("sessions.lastUsed", { date: formatDateTime(session.last_used_at, i18n.language) })}
                </p>
              </div>
            </div>
            <span className="flex size-8 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-colors group-hover:bg-error/10 group-hover:text-error">
              <Trash2 className="size-4" />
            </span>
          </Pressable>
        );
      })}
    </div>
  );
}
