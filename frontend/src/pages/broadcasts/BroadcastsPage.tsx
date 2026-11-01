import { ChevronRight, Plus, Send } from "lucide-react";
import type { ParseKeys } from "i18next";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import {
  DEFAULT_PAGE_SIZE,
  getBroadcastSummary,
  listBroadcasts,
  type Broadcast,
  type BroadcastStatus,
} from "@entities/broadcasts/api";
import {
  audienceSummary,
  BROADCAST_STATUS_TONE,
  broadcastMeta,
  broadcastTitle,
  isEditable,
  processedCount,
} from "@entities/broadcasts/display";
import { listPlans } from "@entities/plans/api";
import { usePermissions } from "@entities/user/use-current-user";
import { formatPercent } from "@shared/lib/format";
import { formatDateTime } from "@shared/lib/relative-time";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { useDebouncedValue } from "@shared/lib/use-debounced-value";
import { usePaginatedList } from "@shared/lib/use-paginated-list";
import { useUrlSearch } from "@shared/lib/use-url-search";
import { Badge, type BadgeTone } from "@shared/ui/Badge";
import { Button } from "@shared/ui/Button";
import { Card } from "@shared/ui/Card";
import { ChoiceChip } from "@shared/ui/ChoiceChip";
import { LIST_BODY_CLASS, LIST_HEAD_CLASS } from "@shared/ui/classes";
import { EmptyState, ErrorState } from "@shared/ui/EmptyState";
import { KpiTile } from "@shared/ui/KpiTile";
import { LoadMoreButton } from "@shared/ui/LoadMoreButton";
import { SearchField } from "@shared/ui/SearchField";
import { Spinner } from "@shared/ui/Spinner";
import { ListRow } from "@shared/ui/ListRow";

const FILTER_DEBOUNCE_MS = 300;

const ROW_GRID_CLASSNAME =
  "grid grid-cols-[36px_minmax(0,2.6fr)_120px_minmax(0,1.6fr)_minmax(0,1.6fr)_110px_16px] items-center gap-4";

const FILTERS = [
  { key: "all", statuses: undefined },
  { key: "DRAFT", statuses: ["DRAFT"] },
  { key: "SCHEDULED", statuses: ["SCHEDULED"] },
  { key: "SENDING", statuses: ["SENDING"] },
  { key: "COMPLETED", statuses: ["COMPLETED"] },
  { key: "problems", statuses: ["CANCELED", "FAILED"] },
] as const satisfies readonly { key: string; statuses: readonly BroadcastStatus[] | undefined }[];

type FilterKey = (typeof FILTERS)[number]["key"];

const ICON_TONE_CLASS: Record<BadgeTone, string> = {
  success: "bg-success/10 text-success",
  warning: "bg-warning/10 text-warning",
  error: "bg-error/10 text-error",
  neutral: "bg-white/[0.06] text-muted-foreground",
  accent: "bg-primary/10 text-primary",
  violet: "bg-violet-400/10 text-violet-300",
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
  const [plansState] = useAsyncResource((signal) =>
    permissions.includes("PLANS_VIEW") ? listPlans(signal) : Promise.resolve([]),
  );
  const plans = plansState.kind === "ready" ? plansState.data : [];

  const none = t("common.none");
  const count = (...keys: BroadcastStatus[]) => keys.reduce((sum, key) => sum + (summary?.by_status[key] ?? 0), 0);
  const filterCount = (key: FilterKey): number | undefined => {
    if (!summary) return undefined;
    const statusesOf = FILTERS.find((filter) => filter.key === key)?.statuses;
    return statusesOf ? count(...statusesOf) : Object.values(summary.by_status).reduce((sum, n) => sum + n, 0);
  };
  const share = (part: number, whole: number) => (whole > 0 ? formatPercent(part / whole, i18n.language) : none);

  const visibleItems = state.kind === "ready" ? state.items : [];
  const hasFilters = Boolean(statuses || search);

  const openBroadcast = (b: Broadcast) => {
    navigate(`/dashboard/broadcasts/${b.id}${isEditable(b) ? "/edit" : ""}`);
  };

  const progress = (b: Broadcast): { label: string; percent: number } => {
    const done = processedCount(b);
    const percent = b.total_count > 0 ? Math.round((done / b.total_count) * 100) : 0;
    const ratio = `${done.toLocaleString(i18n.language)} / ${b.total_count.toLocaleString(i18n.language)} · ${percent}%`;
    if (b.status === "DRAFT") return { label: t("broadcasts.progress.draft"), percent: 0 };
    if (b.status === "SCHEDULED" && !b.started_at) return { label: t("broadcasts.progress.waiting"), percent: 0 };
    if (b.status === "FAILED") return { label: t("broadcasts.progress.failed", { ratio }), percent };
    if (b.status === "CANCELED") return { label: t("broadcasts.progress.canceled", { ratio }), percent };
    if (b.status === "COMPLETED") {
      const delivered = t("broadcasts.progress.delivered", { count: b.sent_count.toLocaleString(i18n.language) });
      return {
        label: b.blocked_count
          ? `${delivered} · ${t("broadcasts.progress.blocked", { count: b.blocked_count.toLocaleString(i18n.language) })}`
          : delivered,
        percent: 100,
      };
    }
    return { label: ratio, percent };
  };

  const when = (b: Broadcast): string => {
    if (b.status === "SENDING") return t("broadcasts.when.now");
    if (b.status === "SCHEDULED" && b.scheduled_at) return formatDateTime(b.scheduled_at, i18n.language);
    const started = b.started_at ?? b.completed_at;
    if (b.status !== "DRAFT" && started) return formatDateTime(started, i18n.language);
    return b.updated_at ? t("broadcasts.when.edited", { date: formatDateTime(b.updated_at, i18n.language) }) : none;
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <span className="text-[13px] text-muted-foreground">{t("broadcasts.description")}</span>
        {canCreate && (
          <Button variant="accent" type="button" onClick={() => navigate("/dashboard/broadcasts/new")}>
            <Plus className="size-3.5" />
            {t("broadcasts.create")}
          </Button>
        )}
      </div>

      {canViewSummary && (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
          <KpiTile
            label={t("broadcasts.kpi.sending")}
            value={summary ? String(count("SENDING")) : none}
          />
          <KpiTile
            label={t("broadcasts.kpi.scheduled")}
            value={summary ? String(count("SCHEDULED")) : none}
            hint={
              summary?.next_scheduled_at
                ? t("broadcasts.kpi.nextScheduled", { date: formatDateTime(summary.next_scheduled_at, i18n.language) })
                : undefined
            }
          />
          <KpiTile
            label={t("broadcasts.kpi.delivered")}
            value={summary ? summary.delivered_30d.toLocaleString(i18n.language) : none}
            hint={
              summary
                ? t("broadcasts.kpi.deliveredShare", { percent: share(summary.delivered_30d, summary.processed_30d) })
                : undefined
            }
          />
          <KpiTile
            label={t("broadcasts.kpi.optedOut")}
            value={summary ? summary.opted_out.toLocaleString(i18n.language) : none}
            hint={
              summary
                ? t("broadcasts.kpi.optedOutShare", { percent: share(summary.opted_out, summary.reachable_customers) })
                : undefined
            }
          />
          <div className="col-span-2 flex lg:col-span-1 [&>*]:flex-1">
            <KpiTile
              label={t("broadcasts.kpi.reachableByEmail")}
              value={summary ? summary.reachable_by_email.toLocaleString(i18n.language) : none}
            />
          </div>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        {FILTERS.map(({ key }) => {
          const n = filterCount(key);
          return (
            <ChoiceChip key={key} active={filterKey === key} onClick={() => setFilterKey(key)}>
              {t(`broadcasts.filters.${key}` as ParseKeys)}
              {n !== undefined && <span className="text-[11px] tabular-nums opacity-70">{n}</span>}
            </ChoiceChip>
          );
        })}
        <div className="ml-auto w-full sm:w-64">
          <SearchField
            id="broadcasts-search"
            label={t("broadcasts.search")}
            hideLabel
            placeholder={t("broadcasts.search")}
            value={searchInput}
            onChange={setSearchInput}
          />
        </div>
      </div>

      <Card>
        {state.kind === "loading" && <Spinner size="page" />}
        {state.kind === "error" && <ErrorState text={t("common.loadError")} size="page" />}
        {state.kind === "ready" && visibleItems.length === 0 && (
          <div className="flex flex-col items-center gap-3">
            <EmptyState text={t(hasFilters ? "broadcasts.noMatches" : "broadcasts.empty")} size="page" />
            {canCreate && !hasFilters && (
              <Button variant="accent" type="button" onClick={() => navigate("/dashboard/broadcasts/new")}>
                <Plus className="size-3.5" />
                {t("broadcasts.create")}
              </Button>
            )}
          </div>
        )}
        {state.kind === "ready" && visibleItems.length > 0 && (
          <div className="overflow-x-auto">
            <div className="min-w-[900px]">
              <div className={`${ROW_GRID_CLASSNAME} ${LIST_HEAD_CLASS}`}>
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
                  const { label, percent } = progress(b);
                  return (
                    <ListRow
                      key={b.id}
                      type="button"
                      disabled={!canOpen}
                      onClick={() => openBroadcast(b)}
                      className={`${ROW_GRID_CLASSNAME} ${canOpen ? "" : "cursor-default"}`}
                    >
                      <span className={`flex size-9 items-center justify-center rounded-full ${ICON_TONE_CLASS[tone]}`}>
                        <Send className="size-4" />
                      </span>
                      <span className="min-w-0">
                        <span className="flex min-w-0 items-center gap-1.5">
                          <span className="truncate text-[13px] font-semibold text-foreground">
                            {broadcastTitle(b, t("broadcasts.untitled"))}
                          </span>
                          {b.category === "MARKETING" && <Badge tone="violet">{t("broadcasts.promoBadge")}</Badge>}
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
                        <span className="truncate text-[12px] text-muted-foreground">
                          {audienceSummary(b.audience, t, plans)}
                        </span>
                      </span>
                      <span className="flex min-w-0 flex-col gap-1.5">
                        <span className="truncate text-[12.5px] tabular-nums text-foreground">{label}</span>
                        <span className="h-[5px] overflow-hidden rounded-full bg-white/[0.07]">
                          <span
                            className={`block h-full rounded-full ${BAR_TONE_CLASS[tone]}`}
                            style={{ width: `${percent}%` }}
                          />
                        </span>
                      </span>
                      <span className="text-[12.5px] tabular-nums text-foreground/80">{when(b)}</span>
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
      </Card>
    </div>
  );
}
