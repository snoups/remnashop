import { Captions, ChevronRight, Filter } from "lucide-react";
import type { ComponentType } from "react";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  DEFAULT_PAGE_SIZE,
  daysUntil,
  EXPIRING_SOON_DAYS,
  formatLimit,
  formatTraffic,
  listSubscriptions,
  SUBSCRIPTION_STATUS_BADGE_TONE,
  type SubscriptionListItem,
  type SubscriptionRow,
  type SubscriptionStatus,
} from "@entities/subscriptions/api";
import { usePermissions } from "@entities/user/use-current-user";
import { PanelSyncButtons } from "@features/panel-sync/PanelSyncButtons";
import { SubscriptionEditDialog } from "@features/subscription-edit/SubscriptionEditDialog";
import { useEntityChanged } from "@shared/lib/entity-dialogs";
import { usePaginatedList } from "@shared/lib/use-paginated-list";
import { IconCircle } from "@shared/ui/glass/IconCircle";
import { GroupToggle } from "@shared/ui/GroupToggle";
import { ListRow } from "@shared/ui/ListRow";
import { useDebouncedValue } from "@shared/lib/use-debounced-value";
import { useUrlSearch } from "@shared/lib/use-url-search";
import { EmptyState, ErrorState } from "@shared/ui/glass/EmptyState";
import { AnimatedHeight } from "@shared/ui/glass/AnimatedHeight";
import { LoadGate, LoadGateHold } from "@shared/lib/load-gate";
import { dotIcon } from "@shared/ui/option-icons";
import { SelectDropdown } from "@shared/ui/SelectDropdown";
import { LoadMoreButton } from "@shared/ui/LoadMoreButton";
import { SearchField } from "@shared/ui/SearchField";
import { RefetchSpinner, Spinner } from "@shared/ui/Spinner";
import { Badge } from "@shared/ui/Badge";
import { Collapse } from "@shared/ui/Collapse";
import { GLASS_LIST_HEAD_CLASS, LIST_BODY_CLASS, PAGE_CLASS, PAGE_SCROLL_UNDER_BAR_CLASS, PAGE_TOOLBAR_CLASS } from "@shared/ui/classes";
import { formatDate } from "@shared/lib/relative-time";
import { useCollapsedSet } from "@shared/lib/use-collapsed-set";

const STATUSES: SubscriptionStatus[] = ["ACTIVE", "LIMITED", "EXPIRED", "DISABLED", "DELETED"];
const FILTER_DEBOUNCE_MS = 200;
const ROW_GRID_CLASSNAME =
  "grid grid-cols-[32px_minmax(0,1fr)_130px_96px_150px_112px_16px] items-center gap-3";
const INACTIVE_STATUSES: ReadonlySet<SubscriptionStatus> = new Set(["EXPIRED", "DISABLED", "DELETED"]);

const STATUS_DOTS: Record<SubscriptionStatus, ComponentType<{ className?: string }>> = {
  ACTIVE: dotIcon("bg-success"),
  LIMITED: dotIcon("bg-warning"),
  EXPIRED: dotIcon("bg-error"),
  DISABLED: dotIcon("bg-muted-foreground"),
  DELETED: dotIcon("bg-muted-foreground"),
};

type ExpiryGroup = "soon" | "active" | "inactive";
const EXPIRY_GROUPS: ExpiryGroup[] = ["soon", "active", "inactive"];

const GROUP_DOT_CLASSNAME: Record<ExpiryGroup, string> = {
  soon: "bg-warning",
  active: "bg-success",
  inactive: "bg-muted-foreground",
};

// grouped client-side over the loaded pages only; move to a server filter if totals per group matter
function expiryGroup(subscription: SubscriptionListItem): ExpiryGroup {
  const days = daysUntil(subscription.expire_at);
  if (INACTIVE_STATUSES.has(subscription.status) || days < 0) return "inactive";
  return days <= EXPIRING_SOON_DAYS ? "soon" : "active";
}

function expiryToneClassName(days: number): string {
  if (days < 0) return "text-error";
  return days <= EXPIRING_SOON_DAYS ? "text-warning" : "text-muted-foreground";
}

export function SubscriptionsPage() {
  const { t, i18n } = useTranslation();
  const [status, setStatus] = useState("");
  const [searchInput, setSearchInput] = useUrlSearch();
  const [editingSubscription, setEditingSubscription] = useState<SubscriptionRow | null>(null);
  const [collapsedGroups, toggleGroup] = useCollapsedSet<ExpiryGroup>();

  const permissions = usePermissions();
  const canViewDetails = permissions.includes("SUBSCRIPTIONS_DETAIL_VIEW");

  const unlimitedLabel = t("subscriptions.unlimited");

  const debouncedSearch = useDebouncedValue(searchInput, FILTER_DEBOUNCE_MS);
  const hasFilters = Boolean(status || debouncedSearch);
  const baseFilters = useMemo<{ status?: SubscriptionStatus; search?: string }>(
    () => ({
      status: (status || undefined) as SubscriptionStatus | undefined,
      search: debouncedSearch || undefined,
    }),
    [status, debouncedSearch],
  );

  const { state, setState, isFetching, isLoadingMore, hasMore, loadMore: handleLoadMore, reload } = usePaginatedList(
    (filters, page, signal) => listSubscriptions({ ...filters, page, pageSize: DEFAULT_PAGE_SIZE }, signal),
    baseFilters,
  );
  useEntityChanged("subscription", reload);

  const handleSaved = (updated: SubscriptionListItem) => {
    // a plan change answers with a new subscription id; the old row is gone
    if (state.kind === "ready" && !state.items.some((item) => item.id === updated.id)) {
      reload();
      return;
    }
    setState((prev) =>
      prev.kind === "ready"
        ? {
            kind: "ready",
            // a write answers without the owner's name
            items: prev.items.map((item) => (item.id === updated.id ? { ...updated, user_name: item.user_name } : item)),
            total: prev.total,
          }
        : prev,
    );
  };

  const handleDeleted = (subscription: SubscriptionListItem) =>
    setState((prev) =>
      prev.kind === "ready"
        ? { kind: "ready", items: prev.items.filter((item) => item.id !== subscription.id), total: prev.total - 1 }
        : prev,
    );

  const groups = useMemo(
    () =>
      state.kind === "ready"
        ? EXPIRY_GROUPS.map((key) => ({ key, items: state.items.filter((item) => expiryGroup(item) === key) })).filter(
            (group) => group.items.length > 0,
          )
        : [],
    [state],
  );
  const relativeTime = new Intl.RelativeTimeFormat(i18n.language, { numeric: "auto" });

  return (
    // as the transactions page: the filter bar floats over a scroller of its own, whose fade clears the bar
    <div data-fills-main className={PAGE_CLASS}>
      <div className={PAGE_TOOLBAR_CLASS}>
        <SearchField
          id="subscriptions-search"
          label={t("subscriptions.filters.search")}
          hideLabel
          compact
          placeholder={t("subscriptions.filters.searchPlaceholder")}
          value={searchInput}
          onChange={setSearchInput}
        />
        <div className="w-44 min-w-0">
          <SelectDropdown
            id="subscriptions-status"
            value={status}
            onChange={setStatus}
            icon={Filter}
            size="compact"
            glassPopover
            placeholder={t("subscriptions.filters.all")}
            options={[
              { value: "", label: t("subscriptions.filters.all"), icon: Filter },
              ...STATUSES.map((value) => ({
                value,
                label: t(`subscriptions.status.${value}`),
                icon: STATUS_DOTS[value],
              })),
            ]}
          />
        </div>
        <PanelSyncButtons onFinished={reload} />
      </div>

      <div className={`${PAGE_SCROLL_UNDER_BAR_CLASS} flex flex-col gap-5`}>
      <LoadGate>
      <LoadGateHold isLoading={state.kind === "loading"} />
      <div className="glass-panel relative shrink-0 rounded-3xl p-4">
        {state.kind === "ready" && isFetching && <RefetchSpinner />}
        <AnimatedHeight>
        {state.kind === "loading" && <Spinner size="page" />}
        {state.kind === "error" && (
          <ErrorState text={t("common.loadError")} size="page" />
        )}
        {state.kind === "ready" && state.items.length === 0 && (
          <EmptyState text={t(hasFilters ? "subscriptions.noMatches" : "subscriptions.empty")} size="page" />
        )}
        {state.kind === "ready" && state.items.length > 0 && (
          <>
            <div className={`${ROW_GRID_CLASSNAME} ${GLASS_LIST_HEAD_CLASS}`}>
              <span className="col-span-2">{t("subscriptions.columns.subscription")}</span>
              <span>{t("subscriptions.fields.traffic")}</span>
              <span>{t("subscriptions.fields.devices")}</span>
              <span>{t("subscriptions.fields.expires")}</span>
              <span>{t("subscriptions.columns.status")}</span>
              <span />
            </div>
            <div className="flex flex-col gap-3">
              {groups.map((group) => (
                <section key={group.key} className="flex flex-col">
                  <h3>
                    <GroupToggle
                      glass
                      open={!collapsedGroups.has(group.key)}
                      onToggle={() => toggleGroup(group.key)}
                      leading={<span className={`-ml-1 size-1.5 rounded-full ${GROUP_DOT_CLASSNAME[group.key]}`} />}
                      label={t(`subscriptions.groups.${group.key}`)}
                      count={group.items.length}
                    />
                  </h3>
                  <Collapse open={!collapsedGroups.has(group.key)} className={LIST_BODY_CLASS}>
                    {group.items.map((subscription) => {
                      const days = daysUntil(subscription.expire_at);

                      return (
                        <ListRow
                          glass
                          key={subscription.id}
                          type="button"
                          disabled={!canViewDetails}
                          onClick={() => setEditingSubscription(subscription)}
                          className={ROW_GRID_CLASSNAME}
                        >
                          <IconCircle icon={Captions} tone={SUBSCRIPTION_STATUS_BADGE_TONE[subscription.status]} />
                          <span className="min-w-0">
                            <span className="flex min-w-0 items-center gap-1.5">
                              <span className="truncate text-[13px] font-medium text-foreground">
                                {subscription.plan_snapshot.name} #{subscription.id}
                              </span>
                              {subscription.is_trial && (
                                <Badge borderless tone="warning">
                                  {t("subscriptions.trial")}
                                </Badge>
                              )}
                            </span>
                            <span className="block truncate text-[12px] text-muted-foreground">
                              {subscription.user_name ?? t("subscriptions.userLabel", { id: subscription.user_id })}
                            </span>
                          </span>
                          <span className="min-w-0">
                            <span className="block text-[13px] font-medium text-foreground">
                              {formatTraffic(subscription.effective_traffic_limit, unlimitedLabel)}
                            </span>
                            <span className="block truncate text-[12px] text-muted-foreground">
                              {t(`subscriptions.edit.strategy.${subscription.traffic_limit_strategy}`)}
                            </span>
                          </span>
                          <span className="text-[13px] font-medium tabular-nums text-foreground">
                            {formatLimit(subscription.effective_device_limit, unlimitedLabel)}
                          </span>
                          <span className="tabular-nums">
                            <span className="block text-[13px] text-foreground">
                              {formatDate(subscription.expire_at, i18n.language)}
                            </span>
                            <span className={`block text-[12px] ${expiryToneClassName(days)}`}>
                              {relativeTime.format(days, "day")}
                            </span>
                          </span>
                          <span>
                            <Badge borderless tone={SUBSCRIPTION_STATUS_BADGE_TONE[subscription.status]}>
                              {t(`subscriptions.status.${subscription.status}`)}
                            </Badge>
                          </span>
                          {canViewDetails ? <ChevronRight className="size-4 text-muted-foreground" /> : <span />}
                        </ListRow>
                      );
                    })}
                  </Collapse>
                </section>
              ))}
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
          </>
        )}
        </AnimatedHeight>
      </div>
      </LoadGate>
      </div>

      {editingSubscription && (
        <SubscriptionEditDialog
          subscription={editingSubscription}
          userName={editingSubscription.user_name}
          onClose={() => setEditingSubscription(null)}
          onSaved={handleSaved}
          onDeleted={handleDeleted}
        />
      )}

    </div>
  );
}
