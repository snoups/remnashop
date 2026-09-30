import {
  AlertCircle,
  ChevronRight,
  Coins,
  CreditCard,
  Filter,
  Layers,
  Loader2,
  LogIn,
  Package,
  Settings,
  Share2,
  ShieldCheck,
  Ticket,
  Users,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useLocation, useNavigate } from "react-router-dom";

import {
  DEFAULT_PAGE_SIZE,
  type EventLogEntry,
  type EventLogFilters,
  type EventLogLocationState,
  listEventLog,
} from "@entities/event-log/api";
import { describeEntry } from "@entities/event-log/describe-entry";
import { EventTypeIcon } from "@entities/event-log/EventTypeIcon";
import { EventDetailDialog } from "@features/event-details/EventDetailDialog";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { useUrlSearch } from "@shared/lib/use-url-search";
import { useDebouncedValue } from "@shared/lib/use-debounced-value";
import { GroupToggle } from "@shared/ui/GroupToggle";
import { Collapse } from "@shared/ui/Collapse";
import { DatePickerField } from "@shared/ui/DatePickerField";
import { EmptyState } from "@shared/ui/EmptyState";
import { LoadMoreButton } from "@shared/ui/LoadMoreButton";
import { SearchField } from "@shared/ui/SearchField";
import { SelectDropdown } from "@shared/ui/SelectDropdown";
import { Spinner } from "@shared/ui/Spinner";
import { Card } from "@shared/ui/Card";
import { EYEBROW_CLASS, LIST_BODY_CLASS, LIST_ROW_CLASS } from "@shared/ui/classes";

type LoadState =
  | { kind: "loading" }
  | { kind: "error" }
  | { kind: "ready"; items: EventLogEntry[]; total: number };

// Mirrors `EventCategory` (backend/app/core/events.py), in sidebar order.
const CATEGORIES = [
  "USER",
  "SUBSCRIPTION",
  "PLANS",
  "PRICING",
  "PROMOCODE",
  "REFERRAL",
  "PAYMENT",
  "AUTH",
  "ADMIN_MANAGEMENT",
  "SETTINGS",
] as const;
const CATEGORY_ICONS: Record<(typeof CATEGORIES)[number], LucideIcon> = {
  AUTH: LogIn,
  ADMIN_MANAGEMENT: ShieldCheck,
  USER: Users,
  SETTINGS: Settings,
  SUBSCRIPTION: Layers,
  PROMOCODE: Ticket,
  REFERRAL: Share2,
  PRICING: Coins,
  PLANS: Package,
  PAYMENT: CreditCard,
};
const CATEGORY_LABEL_KEYS: Record<(typeof CATEGORIES)[number], string> = {
  AUTH: "eventLog.filters.categoryAuth",
  ADMIN_MANAGEMENT: "eventLog.filters.categoryAdminManagement",
  USER: "eventLog.filters.categoryUser",
  SETTINGS: "eventLog.filters.categorySettings",
  SUBSCRIPTION: "eventLog.filters.categorySubscription",
  PROMOCODE: "eventLog.filters.categoryPromocode",
  REFERRAL: "eventLog.filters.categoryReferral",
  PRICING: "eventLog.filters.categoryPricing",
  PLANS: "eventLog.filters.categoryPlans",
  PAYMENT: "eventLog.filters.categoryPayment",
};
const FILTER_DEBOUNCE_MS = 200;
// Only surface the dimmed-loading state once a refetch has been in flight
// this long -- most requests resolve well under it, so typing quickly no
// longer flashes the list dim/opaque on every keystroke pause.
const FETCH_INDICATOR_DELAY_MS = 150;
interface DayGroup {
  key: string;
  date: Date;
  entries: EventLogEntry[];
}

// Entries arrive sorted by occurred_at desc, so consecutive grouping is enough.
function groupByDay(entries: EventLogEntry[]): DayGroup[] {
  const groups: DayGroup[] = [];
  for (const entry of entries) {
    const date = new Date(entry.occurred_at);
    const key = date.toDateString();
    const last = groups[groups.length - 1];
    if (last?.key === key) last.entries.push(entry);
    else groups.push({ key, date, entries: [entry] });
  }
  return groups;
}

export function EventLogPage() {
  const { t, i18n } = useTranslation();
  const bounceStrength = useBounceStrength();
  const [state, setState] = useState<LoadState>({ kind: "loading" });
  const [isFetching, setIsFetching] = useState(false);
  const [category, setCategory] = useState("");
  const [searchInput, setSearchInput] = useUrlSearch();
  const [dateFromInput, setDateFromInput] = useState("");
  const [dateToInput, setDateToInput] = useState("");
  const [page, setPage] = useState(1);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  // opened from elsewhere (notifications bell) with a specific event to show
  const [selectedEntry, setSelectedEntry] = useState<EventLogEntry | null>(
    () => (location.state as EventLogLocationState | null)?.entry ?? null,
  );
  // Bumped on every primary load; a load-more from before a filter change
  // discards its result instead of appending to an already-replaced list.
  const loadGenRef = useRef(0);

  const debouncedSearch = useDebouncedValue(searchInput, FILTER_DEBOUNCE_MS);
  const debouncedDateFrom = useDebouncedValue(dateFromInput, FILTER_DEBOUNCE_MS);
  const debouncedDateTo = useDebouncedValue(dateToInput, FILTER_DEBOUNCE_MS);

  const baseFilters = useMemo<Omit<EventLogFilters, "page" | "pageSize">>(
    () => ({
      category: category || undefined,
      search: debouncedSearch || undefined,
      dateFrom: debouncedDateFrom || undefined,
      dateTo: debouncedDateTo || undefined,
    }),
    [category, debouncedSearch, debouncedDateFrom, debouncedDateTo],
  );

  useEffect(() => {
    const controller = new AbortController();
    const showFetchingTimeout = setTimeout(() => {
      if (!controller.signal.aborted) setIsFetching(true);
    }, FETCH_INDICATOR_DELAY_MS);
    loadGenRef.current += 1;
    setPage(1);
    listEventLog({ ...baseFilters, page: 1, pageSize: DEFAULT_PAGE_SIZE }, controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) {
          setState({ kind: "ready", items: result.items, total: result.total });
        }
      })
      .catch(() => {
        // keep showing whatever's already on screen; only surface the error
        // state when there's nothing else to show
        if (!controller.signal.aborted) {
          setState((prev) => (prev.kind === "ready" ? prev : { kind: "error" }));
        }
      })
      .finally(() => {
        clearTimeout(showFetchingTimeout);
        if (!controller.signal.aborted) setIsFetching(false);
      });
    return () => {
      controller.abort();
      clearTimeout(showFetchingTimeout);
    };
  }, [baseFilters]);

  const handleLoadMore = async () => {
    const gen = loadGenRef.current;
    const nextPage = page + 1;
    setIsLoadingMore(true);
    try {
      const result = await listEventLog({ ...baseFilters, page: nextPage, pageSize: DEFAULT_PAGE_SIZE });
      if (gen !== loadGenRef.current) return;
      setState((prev) =>
        prev.kind === "ready"
          ? { kind: "ready", items: [...prev.items, ...result.items], total: result.total }
          : prev,
      );
      setPage(nextPage);
    } catch {
      // keep current items on failure; the load-more button stays available to retry
    } finally {
      setIsLoadingMore(false);
    }
  };

  const hasMore = state.kind === "ready" && state.items.length < state.total;
  const groups = useMemo(() => (state.kind === "ready" ? groupByDay(state.items) : []), [state]);
  const [collapsedDays, setCollapsedDays] = useState<ReadonlySet<string>>(new Set());
  const toggleDay = (key: string) =>
    setCollapsedDays((prev) => {
      const next = new Set(prev);
      if (!next.delete(key)) next.add(key);
      return next;
    });

  const formatDay = (date: Date): string => {
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(today.getDate() - 1);
    if (date.toDateString() === today.toDateString()) return t("payments.today");
    if (date.toDateString() === yesterday.toDateString()) return t("payments.yesterday");
    return date.toLocaleDateString(i18n.language, {
      day: "numeric",
      month: "long",
      year: date.getFullYear() === today.getFullYear() ? undefined : "numeric",
    });
  };

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <div className="flex flex-wrap items-end gap-3">
          <SearchField
            id="event-log-actor"
            label={t("eventLog.filters.actor")}
            placeholder={t("eventLog.filters.actorPlaceholder")}
            value={searchInput}
            onChange={setSearchInput}
          />

          <div className="flex w-44 shrink-0 flex-col gap-1.5">
            <label className={EYEBROW_CLASS}>{t("eventLog.filters.category")}</label>
            <SelectDropdown
              id="event-log-category"
              value={category}
              onChange={setCategory}
              icon={Filter}
              placeholder={t("eventLog.filters.categoryAll")}
              options={[
                { value: "", label: t("eventLog.filters.categoryAll"), icon: Filter },
                ...CATEGORIES.map((cat) => ({
                  value: cat,
                  label: t(CATEGORY_LABEL_KEYS[cat]),
                  icon: CATEGORY_ICONS[cat],
                })),
              ]}
            />
          </div>

          <div className="flex w-44 shrink-0 flex-col gap-1.5">
            <label className={EYEBROW_CLASS}>{t("eventLog.filters.dateFrom")}</label>
            <DatePickerField
              id="event-log-date-from"
              value={dateFromInput}
              onChange={setDateFromInput}
              placeholder={t("eventLog.filters.dateFrom")}
              clearAriaLabel={t("eventLog.filters.clearDate")}
            />
          </div>

          <div className="flex w-44 shrink-0 flex-col gap-1.5">
            <label className={EYEBROW_CLASS}>{t("eventLog.filters.dateTo")}</label>
            <DatePickerField
              id="event-log-date-to"
              value={dateToInput}
              onChange={setDateToInput}
              placeholder={t("eventLog.filters.dateTo")}
              clearAriaLabel={t("eventLog.filters.clearDate")}
            />
          </div>
        </div>
      </Card>

      <Card className="relative">
        {state.kind === "ready" && isFetching && (
          <Loader2 className="absolute right-4 top-4 size-3.5 animate-spin text-muted-foreground" />
        )}
        {state.kind === "loading" && <Spinner size="page" />}
        {state.kind === "error" && (
          <div className="flex flex-col items-center gap-2 py-12 text-error">
            <AlertCircle className="size-5" />
            <p className="text-sm">{t("eventLog.loadError")}</p>
          </div>
        )}
        {state.kind === "ready" && (
          <>
            {state.items.length === 0 && (
              <EmptyState text={t("eventLog.empty")} size="page" />
            )}
            {state.items.length > 0 && (
              <>
                {/* overflow-y-hidden: overflow-x-auto alone makes y scrollable too, and the rows' rise-in (list-rows) would flash a scrollbar */}
                <div className="-mx-2 overflow-x-auto overflow-y-hidden">
                  {/* px-2 reserves headroom so the rows' whileTap scale (below) grows into
                      padding, not past this track's own box -- keeps the scroll container's
                      measured width stable and avoids a scrollbar flicker on tap. */}
                  <div className="min-w-[640px] px-2">
                    <div className="grid grid-cols-[1.2fr_170px_1fr_140px_16px] gap-4 border-b border-border px-3 pb-2.5">
                      <span className={EYEBROW_CLASS}>
                        {t("eventLog.columns.eventType")}
                      </span>
                      <span className={EYEBROW_CLASS}>
                        {t("eventLog.columns.occurredAt")}
                      </span>
                      <span className={EYEBROW_CLASS}>{t("eventLog.columns.actor")}</span>
                      <span className={EYEBROW_CLASS}>{t("eventLog.detail.ip")}</span>
                    </div>
                    <div className="mt-1 flex flex-col gap-3">
                      {groups.map((group) => (
                        <section key={group.key} className="flex flex-col">
                          <h3>
                            <GroupToggle
                              open={!collapsedDays.has(group.key)}
                              onToggle={() => toggleDay(group.key)}
                              label={formatDay(group.date)}
                              count={group.entries.length}
                            />
                          </h3>
                          <Collapse open={!collapsedDays.has(group.key)} className={`${LIST_BODY_CLASS}`}>
                          {group.entries.map((entry) => (
                            <motion.div
                              key={entry.id}
                              role="button"
                              tabIndex={0}
                              onClick={() => setSelectedEntry(entry)}
                              onKeyDown={(event) => {
                                if (event.key === "Enter" || event.key === " ") {
                                  event.preventDefault();
                                  setSelectedEntry(entry);
                                }
                              }}
                              {...bounceTap(bounceStrength, 0.03)}
                              className={`grid cursor-pointer grid-cols-[1.2fr_170px_1fr_140px_16px] items-center gap-4 ${LIST_ROW_CLASS} hover:bg-white/[0.04]`}
                            >
                              <span className="flex min-w-0 items-center gap-3 text-[13.5px] font-medium text-foreground/90">
                                <span
                                  aria-hidden
                                  className="flex size-9 shrink-0 items-center justify-center rounded-full bg-white/[0.06] text-foreground"
                                >
                                  <EventTypeIcon eventType={entry.event_type} className="size-4" />
                                </span>
                                <span className="truncate">{t(`eventLog.events.${entry.event_type}`)}</span>
                              </span>
                              <span className="text-[13px] tabular-nums text-foreground">
                                {new Date(entry.occurred_at).toLocaleTimeString(i18n.language, {
                                  hour: "2-digit",
                                  minute: "2-digit",
                                })}
                              </span>
                              <span className="truncate text-[12.5px] text-foreground">
                                {describeEntry(entry, t)}
                              </span>
                              <span className="truncate font-mono text-[12.5px] text-foreground">
                                {entry.ip_address ?? "—"}
                              </span>
                              <ChevronRight className="size-4 text-muted-foreground" />
                            </motion.div>
                          ))}
                          </Collapse>
                        </section>
                      ))}
                    </div>
                  </div>
                </div>
                {state.kind === "ready" && hasMore && (
                  <div className="mx-3 mt-4">
                    <LoadMoreButton
                      onClick={() => void handleLoadMore()}
                      isLoading={isLoadingMore}
                      shown={state.items.length}
                      total={state.total}
                    />
                  </div>
                )}
              </>
            )}
          </>
        )}
      </Card>

      {selectedEntry && (
        <EventDetailDialog
          entry={selectedEntry}
          onClose={() => {
            setSelectedEntry(null);
            // drop the entry so a reload/back doesn't reopen the dialog
            if (location.state) navigate({ search: location.search }, { replace: true, state: null });
          }}
        />
      )}
    </div>
  );
}
