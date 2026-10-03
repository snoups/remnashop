import { Bell, Play } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { RefObject } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { listAnnouncements, localized, markAnnouncementsSeen } from "@entities/announcements/api";
import type { Announcement } from "@entities/announcements/api";
import { AnnouncementIcon } from "@entities/announcements/AnnouncementIcon";
import { getNotifications, markNotificationsRead } from "@entities/event-log/api";
import type { EventLogEntry, EventLogLocationState, Notifications } from "@entities/event-log/api";
import { describeEntry } from "@entities/event-log/describe-entry";
import { EventTypeIcon } from "@entities/event-log/EventTypeIcon";
import { usePermissions } from "@entities/user/use-current-user";
import { formatRelative } from "@shared/lib/relative-time";
import { EmptyState } from "@shared/ui/EmptyState";
import { Spinner } from "@shared/ui/Spinner";
import { IconButton } from "@shared/ui/IconButton";
import { PortalPopover } from "@shared/ui/PortalPopover";
import { AnnouncementsCarousel } from "@widgets/announcements/AnnouncementsCarousel";

// plain polling, move to SSE/websocket if the bell needs to be instant
const POLL_INTERVAL_MS = 60_000;
const MAX_BADGE = 9;
const POPOVER_MAX_HEIGHT = 420;
const MAX_SEEN_IDS = 100;

type Row =
  | { kind: "announcement"; at: string; item: Announcement }
  | { kind: "event"; at: string; item: EventLogEntry; index: number };

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
  const permissions = usePermissions();
  const canView = permissions.includes("NOTIFICATIONS_VIEW");
  const canOpenLog = permissions.includes("EVENT_LOG_VIEW");

  const [data, setData] = useState<Notifications | null>(null);
  const [loadFailed, setLoadFailed] = useState(false);
  // how many of the newest items were unread when the popover opened -- they
  // keep their dot while it stays open, even though the server now says 0
  const [highlighted, setHighlighted] = useState(0);
  const [announcements, setAnnouncements] = useState<Announcement[]>([]);
  const [announcementsLoaded, setAnnouncementsLoaded] = useState(false);
  const [announcementsFailed, setAnnouncementsFailed] = useState(false);
  const [highlightedAnnouncements, setHighlightedAnnouncements] = useState<Set<string>>(new Set());
  const [carousel, setCarousel] = useState<{ stories: Announcement[]; index: number } | null>(null);
  const autoOpened = useRef(false);

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

  useEffect(() => {
    const controller = new AbortController();
    const load = () =>
      listAnnouncements(controller.signal).then(
        (result) => {
          setAnnouncements(result.items);
          setAnnouncementsLoaded(true);
          setAnnouncementsFailed(false);
        },
        () => {
          if (!controller.signal.aborted) setAnnouncementsFailed(true);
        },
      );
    load();
    const timer = setInterval(load, POLL_INTERVAL_MS);
    return () => {
      controller.abort();
      clearInterval(timer);
    };
  }, []);

  // the server sorts newest first
  const stories = useMemo(() => announcements.filter((a) => a.slides.length > 0), [announcements]);

  const openStory = useCallback(
    (id: string) => {
      const index = stories.findIndex((a) => a.id === id);
      if (index >= 0) setCarousel({ stories, index });
    },
    [stories],
  );

  useEffect(() => {
    // only the first load may auto-open, never over a carousel or mid-session
    if (!announcementsLoaded || autoOpened.current) return;
    autoOpened.current = true;
    if (carousel) return;
    const target = stories.find((a) => a.auto_open && !a.seen);
    if (!target) return;
    openStory(target.id);
    setAnnouncements((items) => items.map((a) => (a.id === target.id ? { ...a, seen: true } : a)));
    void markAnnouncementsSeen([target.id]).catch(() => {});
  }, [announcementsLoaded, carousel, stories, openStory]);

  useEffect(() => {
    if (!isOpen) return;
    const unseen = announcements.filter((a) => !a.seen).map((a) => a.id);
    if (unseen.length === 0) return;
    setHighlightedAnnouncements(new Set(unseen));
    setAnnouncements((items) => items.map((a) => ({ ...a, seen: true })));
    // the rest are marked on the next open
    void markAnnouncementsSeen(unseen.slice(0, MAX_SEEN_IDS)).catch(() => {});
  }, [isOpen, announcements]);

  const unread = (data?.unread_count ?? 0) + announcements.filter((a) => !a.seen).length;
  const rows: Row[] = [
    ...announcements.map((item) => ({ kind: "announcement" as const, at: item.notify_at, item })),
    ...(canView ? (data?.items ?? []) : []).map((item, index) => ({
      kind: "event" as const,
      at: item.occurred_at,
      item,
      index,
    })),
  ].sort((a, b) => Date.parse(b.at) - Date.parse(a.at));
  const loading = !announcementsLoaded && (canView ? data === null && !loadFailed : !announcementsFailed);

  const openEntry = (state?: EventLogLocationState) => {
    onClose();
    setHighlighted(0);
    setHighlightedAnnouncements(new Set());
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
          {loading ? (
            <Spinner size="card" />
          ) : rows.length === 0 ? (
            announcementsFailed && (!canView || loadFailed) ? (
              <p className="px-2.5 py-8 text-center text-[12.5px] text-error">{t("header.notificationsLoadError")}</p>
            ) : (
              <EmptyState text={t("header.notificationsEmpty")} icon={Bell} />
            )
          ) : (
            rows.map((row) => {
              if (row.kind === "event") {
                const entry = row.item;
                return (
                  <button
                    key={`event-${entry.id}`}
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
                    {row.index < highlighted && <span className="size-1.5 shrink-0 rounded-full bg-primary" />}
                  </button>
                );
              }
              const a = row.item;
              const critical = a.severity === "critical";
              const hasSlides = a.slides.length > 0;
              const text = localized(a.text, i18n.language);
              const cover = a.slides[0]?.image_url;
              const content = (
                <>
                  <span
                    className={`flex size-6 shrink-0 items-center justify-center rounded-full ${
                      critical ? "bg-warning/15 text-warning" : "bg-white/[0.06] text-foreground"
                    }`}
                  >
                    <AnnouncementIcon icon={a.icon} className="size-3.5" />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[12.5px] font-medium text-foreground/90">
                      {localized(a.title, i18n.language)}
                    </span>
                    {text && (
                      <span className="line-clamp-2 text-[11.5px] text-muted-foreground">{text}</span>
                    )}
                    <span className="block truncate text-[11.5px] text-muted-foreground">
                      {critical && `${t("announcements.critical")} · `}
                      {formatRelative(a.notify_at, i18n.language)}
                    </span>
                  </span>
                  {highlightedAnnouncements.has(a.id) && <span className="size-1.5 shrink-0 rounded-full bg-primary" />}
                  {hasSlides && (
                    <span
                      className="relative flex h-[44px] w-[26px] shrink-0 items-center justify-center overflow-hidden rounded-md bg-white/[0.08] bg-cover bg-center"
                      style={cover ? { backgroundImage: `url(${cover})` } : undefined}
                    >
                      <Play className="size-3 fill-white text-white drop-shadow" />
                    </span>
                  )}
                </>
              );
              const rowClass = "flex w-full items-center gap-2.5 rounded-full px-2.5 py-1.5 text-left transition-colors";
              if (hasSlides) {
                return (
                  <button
                    key={`announcement-${a.id}`}
                    type="button"
                    aria-label={t("announcements.openStory")}
                    onClick={() => {
                      onClose();
                      openStory(a.id);
                    }}
                    className={`${rowClass} hover:bg-white/[0.04]`}
                  >
                    {content}
                  </button>
                );
              }
              if (a.url) {
                return (
                  <a
                    key={`announcement-${a.id}`}
                    href={a.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={`${rowClass} hover:bg-white/[0.04]`}
                  >
                    {content}
                  </a>
                );
              }
              return (
                <div key={`announcement-${a.id}`} className={rowClass}>
                  {content}
                </div>
              );
            })
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

      {carousel && (
        <AnnouncementsCarousel stories={carousel.stories} startIndex={carousel.index} onClose={() => setCarousel(null)} />
      )}
    </>
  );
}
