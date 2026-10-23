import type { ParseKeys } from "i18next";
import {
  ChevronRight,
  Coins,
  CreditCard,
  Filter,
  Layers,
  LogIn,
  Megaphone,
  Package,
  Server,
  Settings,
  Share2,
  ShieldCheck,
  Ticket,
  Users,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { motion } from "motion/react";
import { useMemo, useState } from "react";
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
import { usePaginatedList } from "@shared/lib/use-paginated-list";
import { bounceTap } from "@shared/lib/bounceState";
import { useUrlSearch } from "@shared/lib/use-url-search";
import { useDebouncedValue } from "@shared/lib/use-debounced-value";
import { formatTime } from "@shared/lib/relative-time";
import { formatDayLabel, groupByDay } from "@shared/lib/day-groups";
import { useCollapsedSet } from "@shared/lib/use-collapsed-set";
import { GroupToggle } from "@shared/ui/GroupToggle";
import { Collapse } from "@shared/ui/Collapse";
import { DatePickerField } from "@shared/ui/DatePickerField";
import { EmptyState, ErrorState } from "@shared/ui/EmptyState";
import { LoadMoreButton } from "@shared/ui/LoadMoreButton";
import { SearchField } from "@shared/ui/SearchField";
import { SelectDropdown } from "@shared/ui/SelectDropdown";
import { RefetchSpinner, Spinner } from "@shared/ui/Spinner";
import { Card } from "@shared/ui/Card";
import { EYEBROW_CLASS, LIST_BODY_CLASS, LIST_ROW_CLASS } from "@shared/ui/classes";

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
  PAYMENT: CreditCard,
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
      occurredFrom: debouncedDateFrom || undefined,
      occurredTo: debouncedDateTo || undefined,
    }),
    [category, debouncedSearch, debouncedDateFrom, debouncedDateTo],
  );

  const { state, isFetching, isLoadingMore, hasMore, loadMore: handleLoadMore } = usePaginatedList(
    (filters, page, signal) => listEventLog({ ...filters, page, pageSize: DEFAULT_PAGE_SIZE }, signal),
    baseFilters,
  );

  const groups = useMemo(
    () => (state.kind === "ready" ? groupByDay(state.items, (item) => item.occurred_at) : []),
    [state],
  );
  const [collapsedDays, toggleDay] = useCollapsedSet();

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
            />
          </div>

          <div className="flex w-44 shrink-0 flex-col gap-1.5">
            <label className={EYEBROW_CLASS}>{t("eventLog.filters.dateTo")}</label>
            <DatePickerField
              id="event-log-date-to"
              value={dateToInput}
              onChange={setDateToInput}
              placeholder={t("eventLog.filters.dateTo")}
            />
          </div>
        </div>
      </Card>

      <Card className="relative">
        {state.kind === "ready" && isFetching && <RefetchSpinner />}
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
                {/* overflow-y-hidden: overflow-x-auto alone makes y scrollable too, and the rows' rise-in (list-rows) would flash a scrollbar */}
                <div className="-mx-2 overflow-x-auto overflow-y-hidden">
                  {/* px-2: the rows' whileTap scale grows into padding, so the scroll
                      container's width holds and no scrollbar flickers on tap */}
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
                              label={formatDayLabel(group.date, t, i18n.language)}
                              count={group.items.length}
                            />
                          </h3>
                          <Collapse open={!collapsedDays.has(group.key)} className={`${LIST_BODY_CLASS}`}>
                          {group.items.map((entry) => (
                            <motion.div
                              key={entry.id}
                              tabIndex={0}
                              onClick={() => setSelectedEntry(entry)}
                              onKeyDown={(event) => {
                                if (event.key === "Enter" || event.key === " ") {
                                  event.preventDefault();
                                  setSelectedEntry(entry);
                                }
                              }}
                              {...bounceTap(0.03)}
                              className={`grid cursor-pointer grid-cols-[1.2fr_170px_1fr_140px_16px] items-center gap-4 ${LIST_ROW_CLASS} hover:bg-white/[0.04]`}
                            >
                              <span className="flex min-w-0 items-center gap-3 text-[13px] font-medium text-foreground/90">
                                <span
                                  className="flex size-9 shrink-0 items-center justify-center rounded-full bg-white/[0.06] text-foreground"
                                >
                                  <EventTypeIcon eventType={entry.event_type} className="size-4" />
                                </span>
                                <span className="truncate">{t(`eventLog.events.${entry.event_type}` as ParseKeys)}</span>
                              </span>
                              <span className="text-[13px] tabular-nums text-foreground">
                                {formatTime(entry.occurred_at, i18n.language)}
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
