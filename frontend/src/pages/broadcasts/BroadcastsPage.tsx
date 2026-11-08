import { BellOff, CalendarClock, ChevronRight, CircleAlert, CircleCheck, CircleX, Filter, Mail, Megaphone, PencilLine, Play, Plus, Send } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { ParseKeys } from "i18next";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import {
  DEFAULT_PAGE_SIZE,
  getBroadcastSummary,
  listBroadcasts,
  type Broadcast,
  type BroadcastAudience,
  type BroadcastStatus,
} from "@entities/broadcasts/api";
import {
  audienceParts,
  BROADCAST_STATUS_TONE,
  broadcastMeta,
  broadcastTitle,
  isEditable,
  processedCount,
} from "@entities/broadcasts/display";
import { usePermissions } from "@entities/user/use-current-user";
import { formatDateTime } from "@shared/lib/relative-time";
import { LoadGate, LoadGateHold } from "@shared/lib/load-gate";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { useDebouncedValue } from "@shared/lib/use-debounced-value";
import { usePaginatedList } from "@shared/lib/use-paginated-list";
import { useUrlSearch } from "@shared/lib/use-url-search";
import { Badge, type BadgeTone } from "@shared/ui/Badge";
import { Button } from "@shared/ui/Button";
import { GLASS_LIST_HEAD_CLASS, LIST_BODY_CLASS, LIST_SCROLL_X_CLASS, PAGE_CLASS, PAGE_SCROLL_UNDER_BAR_CLASS, PAGE_TOOLBAR_CLASS, PAGE_TOOLBAR_SEARCH_CLASS } from "@shared/ui/classes";
import { AnimatedHeight } from "@shared/ui/glass/AnimatedHeight";
import { EmptyState, ErrorState } from "@shared/ui/glass/EmptyState";
import { IconCircle } from "@shared/ui/glass/IconCircle";
import { KpiTile } from "@shared/ui/KpiTile";
import { LoadMoreButton } from "@shared/ui/LoadMoreButton";
import { SearchField } from "@shared/ui/SearchField";
import { SelectDropdown } from "@shared/ui/SelectDropdown";
import { Spinner } from "@shared/ui/Spinner";
import { ListRow } from "@shared/ui/ListRow";

const FILTER_DEBOUNCE_MS = 300;

const ROW_GRID_CLASSNAME =
  "grid grid-cols-[32px_minmax(0,2.6fr)_140px_minmax(0,1.6fr)_minmax(0,1.6fr)_110px_16px] items-center gap-3";

// what the broadcast goes out on: Telegram, email, or both
const DELIVERY_ICON: Record<Broadcast["delivery"], LucideIcon> = { TELEGRAM: Send, EMAIL: Mail, ALL: Megaphone };

const FILTERS = [
  { key: "all", statuses: undefined },
  { key: "DRAFT", statuses: ["DRAFT"] },
  { key: "SCHEDULED", statuses: ["SCHEDULED"] },
  { key: "SENDING", statuses: ["SENDING"] },
  { key: "COMPLETED", statuses: ["COMPLETED"] },
  { key: "CANCELED", statuses: ["CANCELED"] },
  { key: "FAILED", statuses: ["FAILED"] },
] as const satisfies readonly { key: string; statuses: readonly BroadcastStatus[] | undefined }[];

type FilterKey = (typeof FILTERS)[number]["key"];

const FILTER_ICON: Record<FilterKey, LucideIcon> = {
  all: Filter,
  DRAFT: PencilLine,
  SCHEDULED: CalendarClock,
  SENDING: Play,
  COMPLETED: CircleCheck,
  CANCELED: CircleX,
  FAILED: CircleAlert,
};

const BAR_TONE_CLASS: Record<BadgeTone, string> = {
  success: "bg-success",
  warning: "bg-warning",
  error: "bg-error",
  neutral: "bg-muted-foreground",
  accent: "bg-primary",
  violet: "bg-violet-300",
};

export function BroadcastsPage() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const permissions = usePermissions();
  const canCreate = permissions.includes("BROADCASTS_CREATE");
  const canViewSummary = permissions.includes("BROADCASTS_SUMMARY_VIEW");
  const canOpen = permissions.includes("BROADCASTS_DETAIL_VIEW");

  const [filterKey, setFilterKey] = useState<FilterKey>("all");
  const [searchInput, setSearchInput] = useUrlSearch();
  const search = useDebouncedValue(searchInput, FILTER_DEBOUNCE_MS).trim();
  const statuses = FILTERS.find((filter) => filter.key === filterKey)?.statuses;
  const filters = useMemo(() => ({ statuses, search }), [statuses, search]);
  const {
    state,
    isLoadingMore,
    hasMore,
    loadMore: handleLoadMore,
  } = usePaginatedList(
    (current, page, signal) =>
      listBroadcasts(
        { statuses: current.statuses ? [...current.statuses] : undefined, search: current.search, page, pageSize: DEFAULT_PAGE_SIZE },
        signal,
      ),
    filters,
  );

  const [summaryState] = useAsyncResource((signal) =>
    canViewSummary ? getBroadcastSummary(signal) : Promise.resolve(null),
  );
  const summary = summaryState.kind === "ready" ? summaryState.data : null;

  const none = t("common.none");
  const count = (...keys: BroadcastStatus[]) => keys.reduce((sum, key) => sum + (summary?.by_status[key] ?? 0), 0);
  const filterCount = (key: FilterKey): number | undefined => {
    if (!summary) return undefined;
    const statusesOf = FILTERS.find((filter) => filter.key === key)?.statuses;
    return statusesOf ? count(...statusesOf) : Object.values(summary.by_status).reduce((sum, n) => sum + n, 0);
  };

  const visibleItems = state.kind === "ready" ? state.items : [];
  const hasFilters = Boolean(statuses || search);

  const openBroadcast = (b: Broadcast) => {
    navigate(`/dashboard/broadcasts/${b.id}${isEditable(b) ? "/edit" : ""}`);
  };

  // processed of all: the status is the badge's, here only the numbers and the bar
  const progress = (b: Broadcast): { label: string; percent: number } => {
    if (b.status === "DRAFT" || (b.status === "SCHEDULED" && !b.started_at)) return { label: none, percent: 0 };
    const done = processedCount(b);
    return {
      label: `${done.toLocaleString(i18n.language)} / ${b.total_count.toLocaleString(i18n.language)}`,
      percent: b.total_count > 0 ? Math.round((done / b.total_count) * 100) : 0,
    };
  };

  const when = (b: Broadcast): string => {
    if (b.status === "SENDING") return t("broadcasts.when.now");
    if (b.status === "SCHEDULED" && b.scheduled_at) return formatDateTime(b.scheduled_at, i18n.language);
    const started = b.started_at ?? b.completed_at;
    if (b.status !== "DRAFT" && started) return formatDateTime(started, i18n.language);
    // a draft: when it was last edited
    return b.updated_at ? formatDateTime(b.updated_at, i18n.language) : none;
  };

  return (
    // as the transactions page: the filter bar floats over a scroller of its own, whose fade clears the bar
    <div data-fills-main className={PAGE_CLASS}>
      <div className={PAGE_TOOLBAR_CLASS}>
        <div className={PAGE_TOOLBAR_SEARCH_CLASS}>
          <SearchField
            id="broadcasts-search"
            placeholder={t("broadcasts.search")}
            value={searchInput}
            onChange={setSearchInput}
          />
        </div>
        <div className="w-56 min-w-0">
          <SelectDropdown
            id="broadcasts-status"
            value={filterKey}
            onChange={(key) => setFilterKey(key as FilterKey)}
            icon={Filter}
            size="compact"
            glassPopover
            placeholder={t("broadcasts.filters.all")}
            options={FILTERS.map(({ key }) => {
              const n = filterCount(key);
              const label = t(`broadcasts.filters.${key}` as ParseKeys);
              return { value: key, label: n === undefined ? label : `${label} · ${n}`, icon: FILTER_ICON[key] };
            })}
          />
        </div>
        {canCreate && (
          <Button variant="glassAccent" type="button" onClick={() => navigate("/dashboard/broadcasts/new")} className="ml-auto">
            <Plus className="size-4" />
            {t("broadcasts.create")}
          </Button>
        )}
      </div>

      <div className={`${PAGE_SCROLL_UNDER_BAR_CLASS} flex flex-col gap-5`}>
      <LoadGate>
      <LoadGateHold isLoading={state.kind === "loading" || summaryState.kind === "loading"} />
      <div className="flex flex-col gap-5">
      {canViewSummary && (
        <div className="grid shrink-0 grid-cols-2 gap-5 lg:grid-cols-4">
          <KpiTile
            panel
            icon={Send}
            label={t("broadcasts.kpi.sending")}
            value={summary ? String(count("SENDING")) : none}
          />
          <KpiTile
            panel
            icon={CalendarClock}
            label={t("broadcasts.kpi.scheduled")}
            value={summary ? String(count("SCHEDULED")) : none}
            hint={
              summary?.next_scheduled_at
                ? t("broadcasts.kpi.nextScheduled", { date: formatDateTime(summary.next_scheduled_at, i18n.language) })
                : undefined
            }
          />
          <KpiTile
            panel
            icon={CircleCheck}
            label={t("broadcasts.kpi.delivered")}
            value={summary ? summary.delivered_30d.toLocaleString(i18n.language) : none}
            hint={
              summary
                ? // "of N sent" moves whole to the next line when it doesn't fit
                  <>
                    {t("broadcasts.kpi.period30")} ·{" "}
                    <span className="whitespace-nowrap">{t("broadcasts.kpi.deliveredOf", { count: summary.processed_30d })}</span>
                  </>
                : undefined
            }
          />
          <KpiTile
            panel
            icon={BellOff}
            label={t("broadcasts.kpi.optedOut")}
            value={summary ? summary.opted_out.toLocaleString(i18n.language) : none}
            hint={
              summary
                ? [
                    t("broadcasts.kpi.optedOutOf", { count: summary.reachable_customers }),
                    ...(summary.reachable_by_email > 0
                      ? [t("broadcasts.kpi.byEmail", { count: summary.reachable_by_email })]
                      : []),
                  ].join(" · ")
                : undefined
            }
          />
        </div>
      )}

      <div className="glass-panel relative shrink-0 rounded-3xl p-4">
        <AnimatedHeight>
        {state.kind === "loading" && <Spinner size="page" />}
        {state.kind === "error" && <ErrorState text={t("common.loadError")} size="page" />}
        {state.kind === "ready" && visibleItems.length === 0 && (
          <EmptyState text={t(hasFilters ? "broadcasts.noMatches" : "broadcasts.empty")} size="page" />
        )}
        {state.kind === "ready" && visibleItems.length > 0 && (
          <div className={LIST_SCROLL_X_CLASS}>
            <div className="min-w-[900px]">
              <div className={`${ROW_GRID_CLASSNAME} ${GLASS_LIST_HEAD_CLASS}`}>
                <span className="col-span-2">{t("broadcasts.columns.broadcast")}</span>
                <span>{t("broadcasts.columns.status")}</span>
                <span>{t("broadcasts.columns.audience")}</span>
                <span>{t("broadcasts.columns.delivery")}</span>
                <span>{t("broadcasts.columns.when")}</span>
                <span />
              </div>
              <div className={LIST_BODY_CLASS}>
                {visibleItems.map((b) => {
                  const tone = BROADCAST_STATUS_TONE[b.status];
                  const DeliveryIcon = DELIVERY_ICON[b.delivery];
                  const { label, percent } = progress(b);
                  return (
                    <ListRow
                      key={b.id}
                      type="button"
                      disabled={!canOpen}
                      onClick={() => openBroadcast(b)}
                      className={`${ROW_GRID_CLASSNAME} ${canOpen ? "" : "cursor-default"}`}
                    >
                      <IconCircle icon={DeliveryIcon} tone={tone} />
                      <span className="min-w-0">
                        <span className="flex min-w-0 items-center gap-1.5">
                          <span className="truncate text-[13px] font-medium text-foreground">
                            {broadcastTitle(b, t("broadcasts.untitled"))}
                          </span>
                        </span>
                        <span className="block truncate text-[12px] text-muted-foreground">{broadcastMeta(b, t)}</span>
                      </span>
                      <span>
                        <Badge tone={tone}>{t(`broadcasts.status.${b.status}`)}</Badge>
                      </span>
                      <span className="flex min-w-0 flex-col gap-0.5">
                        <span className="text-[13px] tabular-nums text-foreground">
                          {b.status === "DRAFT" ? none : b.total_count.toLocaleString(i18n.language)}
                        </span>
                        <AudienceCell audience={b.audience} />
                      </span>
                      <span className="flex min-w-0 flex-col gap-1.5">
                        <span className="truncate text-[13px] tabular-nums text-foreground">{label}</span>
                        <span className="h-[5px] overflow-hidden rounded-full glass-track">
                          <span
                            className={`block h-full rounded-full ${BAR_TONE_CLASS[tone]}`}
                            style={{ width: `${percent}%` }}
                          />
                        </span>
                      </span>
                      <span className="text-[13px] tabular-nums text-foreground">{when(b)}</span>
                      {canOpen ? <ChevronRight className="size-4 text-muted-foreground" /> : <span />}
                    </ListRow>
                  );
                })}
              </div>

              {hasMore && (
                <div className="mx-3 mt-4">
                  <LoadMoreButton
                    onClick={() => void handleLoadMore()}
                    isLoading={isLoadingMore}
                    shown={state.items.length}
                    total={state.total}
                  />
                </div>
              )}
            </div>
          </div>
        )}
        </AnimatedHeight>
      </div>
      </div>
      </LoadGate>
      </div>
    </div>
  );
}

/** How many filters, not which: the broadcast's own page spells them out. Picked customers are
 *  their count, no filters everyone. */
function AudienceCell({ audience }: { audience: BroadcastAudience }) {
  const { t } = useTranslation();
  const filters = audienceParts(audience, t, []).length;
  const text = audience.user_ids.length
    ? t("broadcasts.audience.users", { count: audience.user_ids.length })
    : filters
      ? t("broadcasts.audience.filters", { count: filters })
      : t("broadcasts.audience.all");
  return <span className="truncate text-[12px] text-muted-foreground">{text}</span>;
}
