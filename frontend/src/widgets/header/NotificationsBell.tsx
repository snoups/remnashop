import { Bell } from "lucide-react";
import { useEffect, useState, type RefObject } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import {
  getNotifications,
  markNotificationsRead,
  type EventLogLocationState,
  type Notifications,
} from "@entities/event-log/api";
import { describeEntry } from "@entities/event-log/describe-entry";
import { EventTypeIcon } from "@entities/event-log/EventTypeIcon";
import { useCurrentUser } from "@entities/user/use-current-user";
import { formatRelative } from "@shared/lib/relative-time";
import { EmptyState } from "@shared/ui/EmptyState";
import { Spinner } from "@shared/ui/Spinner";
import { IconButton } from "@shared/ui/IconButton";
import { PortalPopover } from "@shared/ui/PortalPopover";

// plain polling, move to SSE/websocket if the bell needs to be instant
const POLL_INTERVAL_MS = 60_000;
const MAX_BADGE = 9;
const POPOVER_MAX_HEIGHT = 420;

const POPOVER_MOTION = {
  initial: { opacity: 0, scale: 0.85 },
  animate: { opacity: 1, scale: 1 },
  exit: { opacity: 0, scale: 0.85 },
  transition: { duration: 0.15, ease: "easeOut" },
} as const;

interface NotificationsBellProps {
  isOpen: boolean;
  /** the wrapper the parent's click-outside already watches */
  anchorRef: RefObject<HTMLElement | null>;
  popoverRef: RefObject<HTMLDivElement | null>;
  onToggle: () => void;
  onClose: () => void;
}

export function NotificationsBell({ isOpen, anchorRef, popoverRef, onToggle, onClose }: NotificationsBellProps) {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const userState = useCurrentUser();
  const permissions = userState.kind === "ready" ? userState.data.effective_permissions : [];
  const canView = permissions.includes("NOTIFICATIONS_VIEW");
  const canOpenLog = permissions.includes("EVENT_LOG_VIEW");

  const [data, setData] = useState<Notifications | null>(null);
  const [loadFailed, setLoadFailed] = useState(false);
  // how many of the newest items were unread when the popover opened -- they
  // keep their dot while it stays open, even though the server now says 0
  const [highlighted, setHighlighted] = useState(0);

  useEffect(() => {
    if (!canView) return;
    const controller = new AbortController();
    const load = () =>
      getNotifications(controller.signal).then(
        (result) => {
          setData(result);
          setLoadFailed(false);
        },
        () => {
          if (!controller.signal.aborted) setLoadFailed(true);
        },
      );
    load();
    const timer = setInterval(load, POLL_INTERVAL_MS);
    return () => {
      controller.abort();
      clearInterval(timer);
    };
  }, [canView]);

  useEffect(() => {
    if (!isOpen || !data || data.unread_count === 0) return;
    setHighlighted(data.unread_count);
    setData({ ...data, unread_count: 0 });
    void markNotificationsRead().catch(() => {});
  }, [isOpen, data]);

  if (!canView) return null;

  const unread = data?.unread_count ?? 0;

  const openEntry = (state?: EventLogLocationState) => {
    onClose();
    setHighlighted(0);
    navigate("/dashboard/event-log", { state });
  };

  return (
    <>
      <IconButton
        size="9"
        tone="glass"
        bounce={0.12}
        className="relative"
        onClick={onToggle}
        aria-haspopup="menu"
        aria-expanded={isOpen}
        aria-label={unread > 0 ? t("header.notificationsUnread", { count: unread }) : t("header.notifications")}
      >
        <Bell className="size-[17px]" />
        {unread > 0 && (
          <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-error px-1 text-[10px] font-semibold leading-none text-white">
            {unread > MAX_BADGE ? `${MAX_BADGE}+` : unread}
          </span>
        )}
      </IconButton>

      <PortalPopover
        open={isOpen}
        triggerRef={anchorRef}
        popoverRef={popoverRef}
        align="right"
        maxHeight={POPOVER_MAX_HEIGHT}
        {...POPOVER_MOTION}
        className="flex max-h-[420px] w-80 flex-col p-1.5"
      >
        <div className="min-h-0 flex-1 overflow-y-auto">
          {data === null && loadFailed ? (
            <p className="px-2.5 py-8 text-center text-[12.5px] text-error">{t("header.notificationsLoadError")}</p>
          ) : data === null ? (
            <Spinner size="card" />
          ) : data.items.length === 0 ? (
            <EmptyState text={t("header.notificationsEmpty")} icon={Bell} />
          ) : (
            data.items.map((entry, index) => (
              <button
                key={entry.id}
                type="button"
                disabled={!canOpenLog}
                onClick={() => openEntry({ entry })}
                className="flex w-full items-center gap-2.5 rounded-full px-2.5 py-1.5 text-left transition-colors enabled:hover:bg-white/[0.04] disabled:cursor-default"
              >
                <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-white/[0.06] text-foreground">
                  <EventTypeIcon eventType={entry.event_type} className="size-3.5" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[12.5px] font-medium text-foreground/90">
                    {t(`eventLog.events.${entry.event_type}`)}
                  </span>
                  <span className="block truncate text-[11.5px] text-muted-foreground">
                    {describeEntry(entry, t)} · {formatRelative(entry.occurred_at, i18n.language)}
                  </span>
                </span>
                {index < highlighted && (
                  <span aria-hidden className="size-1.5 shrink-0 rounded-full bg-primary" />
                )}
              </button>
            ))
          )}
        </div>
        {canOpenLog && (
          <button
            type="button"
            onClick={() => openEntry()}
            className="mt-1 flex h-9 w-full shrink-0 items-center justify-center rounded-popover-item text-[13px] font-medium text-primary transition-colors hover:bg-white/[0.07]"
          >
            {t("header.openEventLog")}
          </button>
        )}
      </PortalPopover>
    </>
  );
}
