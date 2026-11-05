import { Monitor, MonitorSmartphone, Smartphone, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";

import { formatDateTime } from "@shared/lib/relative-time";
import type { Session } from "@entities/auth/sessions";
import { parseUserAgent } from "@shared/lib/parse-user-agent";
import { EmptyState } from "@shared/ui/glass/EmptyState";
import { Badge } from "@shared/ui/Badge";
import { IconCircle } from "@shared/ui/glass/IconCircle";
import { Pressable } from "@shared/ui/Pressable";

interface SessionListProps {
  sessions: Session[];
  currentSessionId?: number | null;
  onRequestRevoke: (session: Session) => void;
  size?: "default" | "compact";
}

export function SessionList({ sessions, currentSessionId, onRequestRevoke, size = "compact" }: SessionListProps) {
  const { t, i18n } = useTranslation();
  const compact = size === "compact";

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
        const DeviceIcon = os === "iOS" || os === "Android" ? Smartphone : os === "Unknown" ? MonitorSmartphone : Monitor;
        return (
          <Pressable
            key={session.id}
            type="button"
            onClick={() => onRequestRevoke(session)}
            className={`group flex w-full items-center justify-between gap-3 rounded-full text-left transition-colors hover:bg-white/[0.04] ${compact ? "p-2" : "min-h-15 px-3.5 py-2"}`}
          >
            <div className="flex min-w-0 flex-1 items-center gap-3">
              <IconCircle icon={DeviceIcon} />
              <div className="min-w-0">
                <p className={`flex items-center gap-2 text-[13px] font-medium text-foreground ${compact ? "h-4 leading-tight" : "flex-wrap leading-5"}`}>
                  {browser} · {os}
                  {isCurrent && (
                    <Badge borderless tone="accent">
                      {t("sessions.thisDevice")}
                    </Badge>
                  )}
                </p>
                <p className={`text-[12px] text-muted-foreground ${compact ? "leading-tight" : "mt-0.5 break-words leading-4"}`}>
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
