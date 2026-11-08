import type { ParseKeys } from "i18next";
import {
  ChevronRight,
  Coins,
  Filter,
  Layers,
  LogIn,
  Megaphone,
  Package,
  Receipt,
  Server,
  Settings,
  Share2,
  ShieldCheck,
  Ticket,
  Users,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useLocation, useNavigate } from "react-router-dom";

import {
  DEFAULT_PAGE_SIZE,
  type EventLogEntry,
  type EventLogFilters,
  type EventLogLocationState,
  listEventLogAfter,
} from "@entities/event-log/api";
import { describeEntry, eventTitle } from "@entities/event-log/describe-entry";
import { EventTypeIcon } from "@entities/event-log/EventTypeIcon";
import { EventDetailDialog } from "@features/event-details/EventDetailDialog";
import { LoadGate, LoadGateHold } from "@shared/lib/load-gate";
import { usePaginatedList } from "@shared/lib/use-paginated-list";
import { useUrlSearch } from "@shared/lib/use-url-search";
import { useDebouncedValue } from "@shared/lib/use-debounced-value";
import { formatTime } from "@shared/lib/relative-time";
import { lastDayToIso, startToIso } from "@shared/lib/iso-date";
import { formatDayLabel, groupByDay } from "@shared/lib/day-groups";
import { useCollapsedSet } from "@shared/lib/use-collapsed-set";
import { AnimatedHeight } from "@shared/ui/glass/AnimatedHeight";
import { IconCircle } from "@shared/ui/glass/IconCircle";
import { GroupToggle } from "@shared/ui/GroupToggle";
import { Collapse } from "@shared/ui/Collapse";
import { DatePickerField } from "@shared/ui/DatePickerField";
import { EmptyState, ErrorState } from "@shared/ui/glass/EmptyState";
import { LoadMoreButton } from "@shared/ui/LoadMoreButton";
import { SearchField } from "@shared/ui/SearchField";
import { SelectDropdown } from "@shared/ui/SelectDropdown";
import { RefetchSpinner, Spinner } from "@shared/ui/Spinner";
import { GLASS_LIST_HEAD_CLASS, LIST_BODY_CLASS, LIST_SCROLL_X_CLASS, PAGE_CLASS, PAGE_SCROLL_UNDER_BAR_CLASS, PAGE_TOOLBAR_CLASS, PAGE_TOOLBAR_SEARCH_CLASS } from "@shared/ui/classes";
import { ListRow } from "@shared/ui/ListRow";

const ROW_GRID_CLASSNAME = "grid grid-cols-[32px_minmax(0,2fr)_64px_minmax(0,1fr)_140px_16px] items-center gap-3";

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
  "BROADCAST",
  "INFRASTRUCTURE",
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
  PAYMENT: Receipt,
  BROADCAST: Megaphone,
  INFRASTRUCTURE: Server,
};
const CATEGORY_LABEL_KEYS: Record<(typeof CATEGORIES)[number], ParseKeys> = {
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
  BROADCAST: "eventLog.filters.categoryBroadcast",
  INFRASTRUCTURE: "eventLog.filters.categoryInfrastructure",
};
const FILTER_DEBOUNCE_MS = 200;
export function EventLogPage() {
  const { t, i18n } = useTranslation();
  const [category, setCategory] = useState("");
  const [searchInput, setSearchInput] = useUrlSearch();
  const [dateFromInput, setDateFromInput] = useState("");
  const [dateToInput, setDateToInput] = useState("");
  const location = useLocation();
  const navigate = useNavigate();
  // opened from elsewhere (notifications bell) with a specific event to show
  const [selectedEntry, setSelectedEntry] = useState<EventLogEntry | null>(
    () => (location.state as EventLogLocationState | null)?.entry ?? null,
  );

  const debouncedSearch = useDebouncedValue(searchInput, FILTER_DEBOUNCE_MS);
  const debouncedDateFrom = useDebouncedValue(dateFromInput, FILTER_DEBOUNCE_MS);
  const debouncedDateTo = useDebouncedValue(dateToInput, FILTER_DEBOUNCE_MS);

  const hasFilters = Boolean(category || debouncedSearch || debouncedDateFrom || debouncedDateTo);
  const baseFilters = useMemo<Omit<EventLogFilters, "page" | "pageSize">>(
    () => ({
      category: category || undefined,
      search: debouncedSearch || undefined,
      // the day groups below are local days, so the bounds are local midnights too
      occurredFrom: startToIso(debouncedDateFrom) ?? undefined,
      occurredTo: lastDayToIso(debouncedDateTo) ?? undefined,
    }),
    [category, debouncedSearch, debouncedDateFrom, debouncedDateTo],
  );

  const { state, isFetching, isLoadingMore, hasMore, loadMore: handleLoadMore } = usePaginatedList(
    (filters, _page, signal, loaded?: EventLogEntry[]) => listEventLogAfter({ ...filters, pageSize: DEFAULT_PAGE_SIZE }, loaded, signal),
    baseFilters,
  );

  const groups = useMemo(
    () => (state.kind === "ready" ? groupByDay(state.items, (item) => item.occurred_at) : []),
    [state],
  );
  const [collapsedDays, toggleDay] = useCollapsedSet();

  return (
    // as settings: the filter bar floats over a scroller of its own, whose fade clears the bar.
    // Desktop keeps the bar on one line, the 68px under it assumes its 48px.
    <div data-fills-main className={PAGE_CLASS}>
      <div className={PAGE_TOOLBAR_CLASS}>
        <div className={PAGE_TOOLBAR_SEARCH_CLASS}>
          <SearchField
            id="event-log-actor"
            placeholder={t("eventLog.filters.actorPlaceholder")}
            value={searchInput}
            onChange={setSearchInput}
          />
        </div>

        <div className="w-48 min-w-0">
          <SelectDropdown
            id="event-log-category"
            value={category}
            onChange={setCategory}
            icon={Filter}
            size="compact"
            glassPopover
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

        <div className="w-40 min-w-0">
          <DatePickerField
            id="event-log-date-from"
            value={dateFromInput}
            onChange={setDateFromInput}
            placeholder={t("eventLog.filters.dateFrom")}
          />
        </div>

        <div className="w-40 min-w-0">
          <DatePickerField
            id="event-log-date-to"
            value={dateToInput}
            onChange={setDateToInput}
            placeholder={t("eventLog.filters.dateTo")}
          />
        </div>
      </div>

      <div className={PAGE_SCROLL_UNDER_BAR_CLASS}>
      <LoadGate>
      <LoadGateHold isLoading={state.kind === "loading"} />
      <div className="glass-panel relative rounded-3xl p-4">
        {state.kind === "ready" && isFetching && <RefetchSpinner />}
        <AnimatedHeight>
        {state.kind === "loading" && <Spinner size="page" />}
        {state.kind === "error" && (
          <ErrorState text={t("common.loadError")} size="page" />
        )}
        {state.kind === "ready" && (
          <>
            {state.items.length === 0 && (
              <EmptyState text={t(hasFilters ? "eventLog.noMatches" : "eventLog.empty")} size="page" />
            )}
            {state.items.length > 0 && (
              <>
                <div className={LIST_SCROLL_X_CLASS}>
                  <div className="min-w-[640px]">
                    <div className={`${ROW_GRID_CLASSNAME} ${GLASS_LIST_HEAD_CLASS}`}>
                      <span className="col-span-2">{t("eventLog.columns.eventType")}</span>
                      <span>{t("eventLog.columns.occurredAt")}</span>
                      <span>{t("eventLog.columns.actor")}</span>
                      <span>{t("eventLog.detail.ip")}</span>
                    </div>
                    <div className="flex flex-col gap-3">
                      {groups.map((group) => (
                        <section key={group.key} className="flex flex-col">
                          <h3>
                            <GroupToggle
                              glass
                              open={!collapsedDays.has(group.key)}
                              onToggle={() => toggleDay(group.key)}
                              label={formatDayLabel(group.date, t, i18n.language)}
                              count={group.items.length}
                            />
                          </h3>
                          <Collapse open={!collapsedDays.has(group.key)} className={LIST_BODY_CLASS}>
                          {group.items.map((entry) => (
                            <ListRow
                              key={entry.id}
                              onClick={() => setSelectedEntry(entry)}
                              className={ROW_GRID_CLASSNAME}
                            >
                              <IconCircle glyph={<EventTypeIcon eventType={entry.event_type} className="size-4" />} />
                              <span className="truncate text-[13px] font-medium text-foreground/90">{eventTitle(entry, t)}</span>
                              <span className="text-[13px] tabular-nums text-foreground">
                                {formatTime(entry.occurred_at, i18n.language)}
                              </span>
                              <span className="truncate text-[13px] text-foreground">
                                {describeEntry(entry, t)}
                              </span>
                              <span className="truncate font-mono text-[12px] text-muted-foreground">
                                {entry.ip_address ?? "—"}
                              </span>
                              <ChevronRight className="size-4 text-muted-foreground" />
                            </ListRow>
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
        </AnimatedHeight>
      </div>
      </LoadGate>
      </div>

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
