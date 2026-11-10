import { Bell, Play, Trash2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { RefObject } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { dismissAnnouncements, listAnnouncements, localized, markAnnouncementsSeen } from "@entities/announcements/api";
import type { Announcement } from "@entities/announcements/api";
import { AnnouncementIcon } from "@entities/announcements/AnnouncementIcon";
import { clearNotifications, getNotifications, markNotificationsRead } from "@entities/event-log/api";
import type { EventLogLocationState, Notifications } from "@entities/event-log/api";
import { describeEntry, eventTitle } from "@entities/event-log/describe-entry";
import { EventTypeIcon } from "@entities/event-log/EventTypeIcon";
import { usePermissions } from "@entities/user/use-current-user";
import { pollWhileVisible } from "@shared/lib/poll-while-visible";
import { onServiceWorkerMessage } from "@shared/lib/push";
import { formatRelative } from "@shared/lib/relative-time";
import { CellText } from "@shared/ui/CellText";
import { EmptyState } from "@shared/ui/glass/EmptyState";
import { SegmentedPills } from "@shared/ui/SegmentedPills";
import { Spinner } from "@shared/ui/Spinner";
import { IconButton } from "@shared/ui/IconButton";
import { Pressable } from "@shared/ui/Pressable";
import { PortalPopover } from "@shared/ui/PortalPopover";
import { AnnouncementDialog } from "@widgets/announcements/AnnouncementDialog";
import { AnnouncementsCarousel } from "@widgets/announcements/AnnouncementsCarousel";

// fallback for browsers without push; a push reloads the bell at once
const POLL_INTERVAL_MS = 60_000;
const MAX_BADGE = 9;
const POPOVER_MAX_HEIGHT = 420;
const MAX_SEEN_IDS = 100;

type Tab = "news" | "events";

// a popover item: corners follow the popover radius, so tall rows hover cleanly too
const ROW_CLASS =
  "flex w-full items-start gap-2.5 rounded-popover-item px-2.5 py-2 text-left transition-colors";

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
  /** an item of the header's glass capsule: no glass of its own */
  capsule?: boolean;
}

export function NotificationsBell({ isOpen, anchorRef, popoverRef, onToggle, onClose, capsule = false }: NotificationsBellProps) {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const permissions = usePermissions();
  const canView = permissions.includes("NOTIFICATIONS_VIEW");
  const canOpenLog = permissions.includes("EVENT_LOG_VIEW");

  const [data, setData] = useState<Notifications | null>(null);
  const [loadFailed, setLoadFailed] = useState(false);
  // how many of the newest items were unread when the popover opened; they
  // keep their dot while it stays open, though the server now says 0
  const [highlighted, setHighlighted] = useState(0);
  const [announcements, setAnnouncements] = useState<Announcement[]>([]);
  const [announcementsLoaded, setAnnouncementsLoaded] = useState(false);
  const [announcementsFailed, setAnnouncementsFailed] = useState(false);
  const [carousel, setCarousel] = useState<{ stories: Announcement[]; index: number } | null>(null);
  const autoOpened = useRef(false);
  const [tab, setTab] = useState<Tab>("news");
  const [details, setDetails] = useState<Announcement | null>(null);

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
    const stopPolling = pollWhileVisible(load, POLL_INTERVAL_MS);
    const stopListening = onServiceWorkerMessage((message) => {
      if (message.type === "notification") load();
    });
    return () => {
      controller.abort();
      stopPolling();
      stopListening();
    };
  }, [canView]);

  // open on whatever is new (news wins a tie); declared before the mark-read effects so it
  // still sees unread state, and only on the open itself so later polls don't yank the tab
  const wasOpen = useRef(false);
  useEffect(() => {
    if (isOpen && !wasOpen.current) {
      const newsUnread = announcements.some((a) => !a.seen);
      const eventsUnread = canView && (data?.unread_count ?? 0) > 0;
      setTab(!canView || newsUnread || !eventsUnread ? "news" : "events");
    }
    wasOpen.current = isOpen;
  }, [isOpen, announcements, data, canView]);

  // dots mark what was new when the popover opened; once it closes everything is read
  useEffect(() => {
    if (isOpen) return;
    setHighlighted(0);
  }, [isOpen]);


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
    const stopPolling = pollWhileVisible(load, POLL_INTERVAL_MS);
    return () => {
      controller.abort();
      stopPolling();
    };
  }, []);

  // the server sorts newest first
  const stories = useMemo(() => announcements.filter((a) => a.slides.length > 0), [announcements]);

  // news counts as read only once it is opened, not when the bell is
  const markSeen = useCallback((id: string) => {
    setAnnouncements((items) => items.map((a) => (a.id === id ? { ...a, seen: true } : a)));
    void markAnnouncementsSeen([id]).catch(() => {});
  }, []);

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
  }, [announcementsLoaded, carousel, stories, openStory]);

  const unread = (data?.unread_count ?? 0) + announcements.filter((a) => !a.seen).length;
  const events = canView ? (data?.items ?? []) : [];
  // no news, no news tab: the bell is just the event list then
  const showTabs = canView && announcements.length > 0;
  const activeTab: Tab = showTabs ? tab : canView ? "events" : "news";
  const activeCount = activeTab === "news" ? announcements.length : events.length;
  // events count as read only once their tab is actually on screen
  useEffect(() => {
    if (!isOpen || activeTab !== "events" || !data || data.unread_count === 0) return;
    setHighlighted(data.unread_count);
    setData({ ...data, unread_count: 0 });
    void markNotificationsRead().catch(() => {});
  }, [isOpen, activeTab, data]);

  const loading =
    activeTab === "news" ? !announcementsLoaded && !announcementsFailed : data === null && !loadFailed;
  const failed = activeTab === "news" ? announcementsFailed && !announcementsLoaded : loadFailed && data === null;

  const clearActive = () => {
    if (activeTab === "news") {
      const ids = announcements.map((a) => a.id);
      setAnnouncements([]);
        void dismissAnnouncements(ids.slice(0, MAX_SEEN_IDS)).catch(() => {});
      return;
    }
    setData((current) => (current ? { items: [], total: 0, unread_count: 0 } : current));
    setHighlighted(0);
    void clearNotifications().catch(() => {});
  };

  const openEntry = (state?: EventLogLocationState) => {
    onClose();
    setHighlighted(0);
    navigate("/dashboard/events", { state });
  };

  return (
    <>
      <IconButton size="9" tone={capsule ? "default" : "glass"} className="relative" onClick={onToggle}>
        <Bell className="size-4" />
        {unread > 0 && (
          <span className="absolute right-0 top-0 flex h-4 min-w-4 items-center justify-center rounded-full bg-primary px-1 text-[11px] font-semibold leading-none text-primary-foreground">
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
        glass
        extraGap={4}
        className="flex max-h-[min(420px,calc(100dvh-96px-env(safe-area-inset-top)-env(safe-area-inset-bottom)))] flex-col p-1.5 max-md:top-[calc(84px+env(safe-area-inset-top))]! max-md:bottom-auto! max-md:left-2! max-md:right-2! md:max-h-[420px] md:w-80"
      >
        {(showTabs || activeCount > 0) && (
        <div className="flex shrink-0 items-center gap-1.5 pb-1.5">
          {showTabs ? (
            <div className="min-w-0 flex-1">
              {/* 36px, as the clear button: the popover's 24px corner minus its 6px inset */}
              <SegmentedPills<Tab>
                stretch
                compact
                value={activeTab}
                onChange={setTab}
                options={[
                  { value: "news", label: t("header.tabNews"), dot: announcements.some((a) => !a.seen) },
                  { value: "events", label: t("header.tabEvents"), dot: (data?.unread_count ?? 0) > 0 },
                ]}
              />
            </div>
          ) : (
            <span className="min-w-0 flex-1 px-2.5 text-sm font-semibold text-foreground">
              {t(activeTab === "news" ? "header.tabNews" : "header.tabEvents")}
            </span>
          )}
          {activeCount > 0 && (
            <Pressable
              onClick={clearActive}
              className="flex h-9 shrink-0 items-center gap-1.5 rounded-full px-3.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-white/[0.06] hover:text-foreground"
            >
              <Trash2 className="size-4" />
              {t("header.clear")}
            </Pressable>
          )}
        </div>
        )}
        <div
          // no footer under it: the list runs to the popover's edge, its padding is the 6px inset
          className={`scroll-fade-y min-h-0 flex-1 overflow-y-auto pt-2 [--fade-top-size:8px] ${
            canOpenLog && activeTab === "events" ? "pb-2 [--fade-bottom-size:8px]" : "-mb-1.5 pb-1.5 [--fade-bottom-size:6px]"
          }`}
        >
          {loading ? (
            <Spinner size="card" />
          ) : failed ? (
            <p className="px-2.5 py-8 text-center text-xs text-error">{t("header.notificationsLoadError")}</p>
          ) : activeCount === 0 ? (
            <EmptyState text={t("header.notificationsEmpty")} icon={Bell} />
          ) : activeTab === "events" ? (
            events.map((entry, index) => (
              <Pressable
                key={entry.id}
                type="button"
                disabled={!canOpenLog}
                onClick={() => openEntry({ entry })}
                className={`${ROW_CLASS} enabled:hover:bg-white/[0.06] disabled:cursor-default`}
              >
                <span className="mt-px flex size-6 shrink-0 items-center justify-center rounded-full bg-white/[0.06] text-foreground">
                  <EventTypeIcon eventType={entry.event_type} className="size-3.5" />
                </span>
                <CellText
                  title={eventTitle(entry, t)}
                  sub={`${describeEntry(entry, t)} · ${formatRelative(entry.occurred_at, i18n.language)}`}
                  className="flex-1"
                />
                {index < highlighted && <span className="size-1.5 shrink-0 self-center rounded-full bg-primary" />}
              </Pressable>
            ))
          ) : (
            announcements.map((a) => {
              const critical = a.severity === "critical";
              const hasSlides = a.slides.length > 0;
              const text = localized(a.text, i18n.language);
              const cover = a.slides[0]?.image_url;
              const content = (
                <>
                  <span
                    className={`mt-px flex size-6 shrink-0 items-center justify-center rounded-full ${
                      critical ? "bg-warning/15 text-warning" : "bg-white/[0.06] text-foreground"
                    }`}
                  >
                    <AnnouncementIcon icon={a.icon} className="size-3.5" />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium text-foreground">
                      {localized(a.title, i18n.language)}
                    </span>
                    {text && <span className="line-clamp-2 text-xs text-muted-foreground">{text}</span>}
                    <span className="block truncate text-xs text-muted-foreground">
                      {critical && `${t("announcements.critical")} · `}
                      {formatRelative(a.notify_at, i18n.language)}
                    </span>
                  </span>
                  {!a.seen && <span className="size-1.5 shrink-0 self-center rounded-full bg-primary" />}
                  {hasSlides && (
                    <span
                      className="relative flex h-[44px] w-[26px] shrink-0 self-center items-center justify-center overflow-hidden rounded-md bg-white/[0.08] bg-cover bg-center"
                      style={cover ? { backgroundImage: `url("${cover}")` } : undefined}
                    >
                      <Play className="size-3 fill-white text-white drop-shadow" />
                    </span>
                  )}
                </>
              );
              return (
                <Pressable
                  key={a.id}
                  type="button"
                  onClick={() => {
                    onClose();
                    if (hasSlides) openStory(a.id);
                    else {
                      setDetails(a);
                      markSeen(a.id);
                    }
                  }}
                  className={`${ROW_CLASS} hover:bg-white/[0.06]`}
                >
                  {content}
                </Pressable>
              );
            })
          )}
        </div>
        {canOpenLog && activeTab === "events" && (
          <Pressable
            type="button"
            onClick={() => openEntry()}
            className="mt-1 flex h-9 w-full shrink-0 items-center justify-center rounded-popover-item text-sm font-medium text-primary transition-colors hover:bg-white/[0.07]"
          >
            {t("header.openEventLog")}
          </Pressable>
        )}
      </PortalPopover>

      {details && <AnnouncementDialog announcement={details} onClose={() => setDetails(null)} />}

      {carousel && (
        <AnnouncementsCarousel
          stories={carousel.stories}
          startIndex={carousel.index}
          onView={markSeen}
          onClose={() => setCarousel(null)}
        />
      )}
    </>
  );
}
