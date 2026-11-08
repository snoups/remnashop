import { Monitor, MonitorSmartphone, Smartphone, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";

import { formatDateTime } from "@shared/lib/relative-time";
import type { Session } from "@entities/auth/sessions";
import { parseUserAgent } from "@shared/lib/parse-user-agent";
import { EmptyState } from "@shared/ui/glass/EmptyState";
import { Badge } from "@shared/ui/Badge";
import { Row } from "@shared/ui/glass/Row";

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
    <div className={`flex flex-col ${compact ? "" : "divide-y divide-border/50"}`}>
      {sessions.map((session) => {
        const { browser, os } = parseUserAgent(session.user_agent);
        const isCurrent = session.id === currentSessionId;
        const DeviceIcon = os === "iOS" || os === "Android" ? Smartphone : os === "Unknown" ? MonitorSmartphone : Monitor;
        return (
          <Row
            key={session.id}
            size={compact ? "sm" : "md"}
            icon={DeviceIcon}
            label={
              <>
                <span className="truncate">
                  {browser} · {os}
                </span>
                {isCurrent && (
                  <Badge borderless tone="accent">
                    {t("sessions.thisDevice")}
                  </Badge>
                )}
              </>
            }
            description={`${session.ip_address} · ${t("sessions.lastUsed", { date: formatDateTime(session.last_used_at, i18n.language) })}`}
            onClick={() => onRequestRevoke(session)}
          >
            <span
              data-row-button
              className="flex size-8 items-center justify-center rounded-full text-muted-foreground transition-colors group-hover/row:bg-error/10 group-hover/row:text-error"
            >
              <Trash2 className="size-4" />
            </span>
          </Row>
        );
      })}
    </div>
  );
}
