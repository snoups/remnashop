import { AlertCircle, Layers, Loader2, Pencil, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  DEFAULT_PAGE_SIZE,
  deleteSubscription,
  listSubscriptions,
  SUBSCRIPTION_STATUS_BADGE_TONE,
  type SubscriptionListItem,
  type SubscriptionStatus,
} from "@entities/subscriptions/api";
import { usePermissions } from "@entities/user/use-current-user";
import { SubscriptionEditDialog } from "@features/subscription-edit/SubscriptionEditDialog";
import { getErrorMessage } from "@shared/api/http";
import { useEntityChanged } from "@shared/lib/entity-dialogs";
import { usePaginatedList } from "@shared/lib/use-paginated-list";
import { toast } from "@shared/lib/toast";
import { GroupToggle } from "@shared/ui/GroupToggle";
import { ActionMenu, type ActionMenuItem } from "@shared/ui/ActionMenu";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { useDebouncedValue } from "@shared/lib/use-debounced-value";
import { useUrlSearch } from "@shared/lib/use-url-search";
import { EmptyState } from "@shared/ui/EmptyState";
import { LoadMoreButton } from "@shared/ui/LoadMoreButton";
import { SearchField } from "@shared/ui/SearchField";
import { SegmentedPills } from "@shared/ui/SegmentedPills";
import { Spinner } from "@shared/ui/Spinner";
import { Badge } from "@shared/ui/Badge";
import { Card } from "@shared/ui/Card";
import { Collapse } from "@shared/ui/Collapse";
import { LIST_BODY_CLASS, LIST_HEAD_CLASS, LIST_ROW_CLASS } from "@shared/ui/classes";
import { CardHeader } from "@shared/ui/CardHeader";
import { formatDate } from "@shared/lib/relative-time";
import { DAY_MS } from "@shared/lib/period";
import { useCollapsedSet } from "@shared/lib/use-collapsed-set";

const STATUSES: SubscriptionStatus[] = ["ACTIVE", "LIMITED", "EXPIRED", "DISABLED", "DELETED"];
const FILTER_DEBOUNCE_MS = 200;
const ROW_GRID_CLASSNAME =
  "grid grid-cols-[36px_minmax(0,1fr)_130px_96px_150px_112px_32px] items-center gap-3";
const EXPIRING_SOON_DAYS = 7;
const INACTIVE_STATUSES: ReadonlySet<SubscriptionStatus> = new Set(["EXPIRED", "DISABLED", "DELETED"]);

type ExpiryGroup = "soon" | "active" | "inactive";
const EXPIRY_GROUPS: ExpiryGroup[] = ["soon", "active", "inactive"];

const GROUP_DOT_CLASSNAME: Record<ExpiryGroup, string> = {
  soon: "bg-warning",
  active: "bg-success",
  inactive: "bg-muted-foreground",
};

function formatTraffic(gb: number, unlimitedLabel: string): string {
  return gb === 0 ? unlimitedLabel : `${gb} GB`;
}

function formatLimit(value: number, unlimitedLabel: string): string {
  return value === 0 ? unlimitedLabel : String(value);
}

function daysUntil(iso: string): number {
  return Math.ceil((new Date(iso).getTime() - Date.now()) / DAY_MS);
}

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
  const [editingSubscription, setEditingSubscription] = useState<SubscriptionListItem | null>(null);
  const [pendingDelete, setPendingDelete] = useState<SubscriptionListItem | null>(null);
  const [collapsedGroups, toggleGroup] = useCollapsedSet<ExpiryGroup>();

  const permissions = usePermissions();
  const canEdit = permissions.includes("SUBSCRIPTIONS_UPDATE");
  const canDelete = permissions.includes("SUBSCRIPTIONS_DELETE");

  const unlimitedLabel = t("subscriptions.unlimited");

  const debouncedSearch = useDebouncedValue(searchInput, FILTER_DEBOUNCE_MS);
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

  const handleSaved = (updated: SubscriptionListItem) =>
    setState((prev) =>
      prev.kind === "ready"
        ? { kind: "ready", items: prev.items.map((item) => (item.id === updated.id ? updated : item)), total: prev.total }
        : prev,
    );

  const handleDeleted = (subscription: SubscriptionListItem) =>
    setState((prev) =>
      prev.kind === "ready"
        ? { kind: "ready", items: prev.items.filter((item) => item.id !== subscription.id), total: prev.total - 1 }
        : prev,
    );

  const handleDelete = async (subscription: SubscriptionListItem) => {
    try {
      await deleteSubscription(subscription.id);
      handleDeleted(subscription);
    } catch (err) {
      toast.error(getErrorMessage(err, t("subscriptions.delete.error")));
    }
  };

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
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <SegmentedPills
          value={status}
          onChange={setStatus}
          options={[
            { value: "", label: t("subscriptions.filters.all") },
            ...STATUSES.map((s) => ({ value: s, label: t(`subscriptions.status.${s}`) })),
          ]}
        />
        <div className="flex w-80">
          <SearchField
            id="subscriptions-search"
            label={t("subscriptions.filters.search")}
            placeholder={t("subscriptions.filters.searchPlaceholder")}
            value={searchInput}
            onChange={setSearchInput}
          />
        </div>
      </div>

      <Card className="relative">
        {state.kind === "ready" && isFetching && (
          <Loader2 className="absolute right-4 top-4 size-3.5 animate-spin text-muted-foreground" />
        )}
        <CardHeader
          icon={Layers}
          title={
            <>
              {t("subscriptions.title")}
              {state.kind === "ready" && (
                <span className="text-[11.5px] font-normal tabular-nums text-muted-foreground">{state.total}</span>
              )}
            </>
          }
          description={t("subscriptions.description")}
        />

        {state.kind === "loading" && <Spinner size="page" />}
        {state.kind === "error" && (
          <div className="flex flex-col items-center gap-2 py-12 text-error">
            <AlertCircle className="size-5" />
            <p className="text-sm">{t("subscriptions.loadError")}</p>
          </div>
        )}
        {state.kind === "ready" && state.items.length === 0 && (
          <EmptyState text={t("subscriptions.empty")} size="page" />
        )}
        {state.kind === "ready" && state.items.length > 0 && (
          <div className="mt-3">
            <div
              className={`${ROW_GRID_CLASSNAME} ${LIST_HEAD_CLASS}`}
            >
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
                      open={!collapsedGroups.has(group.key)}
                      onToggle={() => toggleGroup(group.key)}
                      leading={<span className={`-ml-1 size-1.5 rounded-full ${GROUP_DOT_CLASSNAME[group.key]}`} />}
                      label={t(`subscriptions.groups.${group.key}`)}
                      count={group.items.length}
                    />
                  </h3>
                  <Collapse open={!collapsedGroups.has(group.key)} className={LIST_BODY_CLASS}>
                    {group.items.map((subscription) => {
                      const squadCount =
                        subscription.internal_squads.length + (subscription.external_squad ? 1 : 0);
                      const days = daysUntil(subscription.expire_at);

                      const menuItems: ActionMenuItem[] = [];
                      if (canEdit) {
                        menuItems.push({
                          label: t("common.edit"),
                          icon: Pencil,
                          onClick: () => setEditingSubscription(subscription),
                        });
                      }
                      if (canDelete) {
                        menuItems.push({
                          label: t("subscriptions.delete.button"),
                          icon: Trash2,
                          variant: "danger",
                          onClick: () => setPendingDelete(subscription),
                        });
                      }

                      return (
                        <div
                          key={subscription.id}
                          className={`${ROW_GRID_CLASSNAME} ${LIST_ROW_CLASS} hover:bg-white/[0.04]`}
                        >
                          <span
                            className={`flex size-9 items-center justify-center rounded-full ${
                              subscription.status === "ACTIVE"
                                ? "bg-primary/10 text-primary"
                                : "bg-white/[0.06] text-muted-foreground"
                            }`}
                          >
                            <Layers className="size-4" />
                          </span>
                          <span className="min-w-0">
                            <span className="flex min-w-0 items-center gap-1.5">
                              <span className="truncate text-[13.5px] font-medium text-foreground">
                                {t("subscriptions.userLabel", { id: subscription.user_id })}
                              </span>
                              {subscription.is_trial && (
                                <Badge tone="warning">
                                  {t("subscriptions.trial")}
                                </Badge>
                              )}
                              {subscription.tag && (
                                <Badge tone="accent">
                                  {subscription.tag}
                                </Badge>
                              )}
                            </span>
                            <span className="block truncate font-mono text-[12px] text-muted-foreground">
                              #{subscription.id} &middot; {t("subscriptions.fields.squads", { count: squadCount })}
                            </span>
                          </span>
                          <span className="min-w-0">
                            <span className="block text-[13px] font-medium text-foreground">
                              {formatTraffic(subscription.effective_traffic_limit, unlimitedLabel)}
                            </span>
                            <span className="block truncate text-[11.5px] text-muted-foreground">
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
                            <span className={`block text-[11.5px] ${expiryToneClassName(days)}`}>
                              {relativeTime.format(days, "day")}
                            </span>
                          </span>
                          <span>
                            <Badge tone={SUBSCRIPTION_STATUS_BADGE_TONE[subscription.status]}>
                              {t(`subscriptions.status.${subscription.status}`)}
                            </Badge>
                          </span>
                          <span className="flex justify-end">
                            {menuItems.length > 0 && <ActionMenu items={menuItems} />}
                          </span>
                        </div>
                      );
                    })}
                  </Collapse>
                </section>
              ))}
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
          </div>
        )}
      </Card>

      {editingSubscription && (
        <SubscriptionEditDialog
          subscription={editingSubscription}
          onClose={() => setEditingSubscription(null)}
          onSaved={handleSaved}
          onDeleted={handleDeleted}
        />
      )}

      {pendingDelete && (
        <ConfirmDialog
          title={t("subscriptions.delete.confirmTitle")}
          message={t("subscriptions.delete.confirm", { id: pendingDelete.id })}
          confirmLabel={t("common.delete")}
          cancelLabel={t("common.cancel")}
          danger
          onConfirm={() => {
            void handleDelete(pendingDelete);
            setPendingDelete(null);
          }}
          onCancel={() => setPendingDelete(null)}
        />
      )}
    </div>
  );
}
