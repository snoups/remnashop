import {
  Ban,
  CircleCheck,
  CreditCard,
  ArrowDown,
  ArrowUp,
  Gift,
  GitMerge,
  History,
  Info,
  KeyRound,
  LaptopMinimal,
  Loader2,
  Mail,
  Send,
  ShieldPlus,
  Trash2,
  type LucideIcon,
} from "lucide-react";
import { motion } from "motion/react";
import { useMemo, useState, type ComponentType } from "react";
import { useTranslation } from "react-i18next";

import {
  DEFAULT_PAGE_SIZE,
  getUserListStats,
  listUsers,
  type UserListFilters,
  type UserListItem,
  type BlockedBy,
  type UserListStats,
  type UserSort,
} from "@entities/user/api";
import { ROLE_BADGE_TONE } from "@entities/admin/display";
import { SUBSCRIPTION_STATUS_BADGE_TONE } from "@entities/subscriptions/api";
import type { SubscriptionStatus } from "@entities/subscriptions/api";
import { UserDetailsDialog } from "@features/user-details/UserDetailsDialog";
import type { UserDetailsTab } from "@features/user-details/UserDetailsDialog";
import { useUserActions } from "@features/user-details/use-user-actions";
import { useEntityChanged } from "@shared/lib/entity-dialogs";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { usePaginatedList } from "@shared/lib/use-paginated-list";
import { formatPercent } from "@shared/lib/format";
import { bounceTap } from "@shared/lib/bounceState";
import { formatDate, formatRelative } from "@shared/lib/relative-time";
import { useUrlSearch } from "@shared/lib/use-url-search";
import { useDebouncedValue } from "@shared/lib/use-debounced-value";
import { initials } from "@shared/lib/initials";
import { useCurrentUser, usePermissions } from "@entities/user/use-current-user";
import { userHandle } from "@features/user-referrals/format";
import { ActionMenu, type ActionMenuItem } from "@shared/ui/ActionMenu";
import { Badge } from "@shared/ui/Badge";
import { Card } from "@shared/ui/Card";
import { EmptyState, ErrorState } from "@shared/ui/EmptyState";
import { KpiTile } from "@shared/ui/KpiTile";
import { LoadMoreButton } from "@shared/ui/LoadMoreButton";
import { SearchField } from "@shared/ui/SearchField";
import { SelectDropdown, type SelectOption } from "@shared/ui/SelectDropdown";
import { dotIcon } from "@shared/ui/optionIcons";
import { Spinner } from "@shared/ui/Spinner";
import { EYEBROW_CLASS, LIST_BODY_CLASS, LIST_HEAD_CLASS, LIST_ROW_CLASS } from "@shared/ui/classes";

type Kpi = "all" | "new" | "subscribed" | "blocked";

const KPIS: Kpi[] = ["all", "new", "subscribed", "blocked"];
const FILTER_DEBOUNCE_MS = 200;

const ROW_GRID_CLASSNAME =
  "grid grid-cols-[36px_minmax(0,1fr)_100px_90px_130px_32px] items-center gap-3";

const YES_DOT = dotIcon("bg-success");
const NO_DOT = dotIcon("bg-muted-foreground");
const BLOCKED_DOT = dotIcon("bg-error");
const LISTS_DOT = dotIcon("bg-warning");

const KPI_STAT: Record<Kpi, keyof UserListStats> = {
  all: "total",
  new: "new",
  subscribed: "subscribed",
  blocked: "blocked",
};

// active, limited, expired; a zero is left out
function subscriptionCounts(user: UserListItem): { status: SubscriptionStatus; count: number }[] {
  return (
    [
      ["ACTIVE", user.active_subscriptions],
      ["LIMITED", user.limited_subscriptions],
      ["EXPIRED", user.expired_subscriptions],
    ] as const
  ).flatMap(([status, count]) => (count ? [{ status, count }] : []));
}

function getAvatarClassName(user: UserListItem, isSelf: boolean): string {
  if (user.deleted_at) return "bg-white/[0.04] text-muted-foreground";
  if (user.is_blocked) return "bg-error/10 text-error";
  if (isSelf) return "bg-accent text-primary";
  return "bg-white/[0.06] text-foreground";
}

// "" = any, otherwise the literal the backend's Optional[bool] query param takes
function parseTriState(value: string): boolean | undefined {
  return value === "" ? undefined : value === "true";
}

function FilterSelect({
  id,
  label,
  icon,
  value,
  onChange,
  options,
}: {
  id: string;
  label: string;
  icon: ComponentType<{ className?: string }>;
  value: string;
  onChange: (value: string) => void;
  options: SelectOption[];
}) {
  return (
    // fixed width: the search field takes the rest of the row
    <div className="flex w-44 shrink-0 flex-col gap-1.5">
      <span className={EYEBROW_CLASS}>{label}</span>
      <SelectDropdown id={id} value={value} onChange={onChange} icon={icon} placeholder={options[0].label} options={options} />
    </div>
  );
}

export function UsersPage() {
  const { t, i18n } = useTranslation();
  const [searchInput, setSearchInput] = useUrlSearch();
  const [blockedBy, setBlockedBy] = useState<BlockedBy | "">("");
  const [subscription, setSubscription] = useState("");
  const [trial, setTrial] = useState("");
  const [sort, setSort] = useState<{ by: UserSort; descending: boolean }>({ by: "created_at", descending: true });

  const currentUserState = useCurrentUser();
  const permissions = usePermissions();
  const currentUserId = currentUserState.kind === "ready" ? currentUserState.data.id : null;
  // staff rows are only listable with ADMINS_MANAGE (see ListUsersUseCase)
  const includeStaff = permissions.includes("ADMINS_MANAGE");
  const [detailsUser, setDetailsUser] = useState<UserListItem | null>(null);
  const [detailsTab, setDetailsTab] = useState<UserDetailsTab>();

  const debouncedSearch = useDebouncedValue(searchInput, FILTER_DEBOUNCE_MS);
  const [statsState, refreshStats] = useAsyncResource((signal) => getUserListStats(includeStaff, signal), {
    deps: [includeStaff],
    keepData: true,
  });
  const stats = statsState.kind === "ready" ? statsState.data : null;

  const hasFilters = Boolean(debouncedSearch || blockedBy || subscription || trial);
  const baseFilters = useMemo<Omit<UserListFilters, "page" | "pageSize">>(
    () => ({
      search: debouncedSearch || undefined,
      includeStaff,
      blockedBy: blockedBy || undefined,
      hasSubscription: parseTriState(subscription),
      isTrialAvailable: parseTriState(trial),
      sort: sort.by,
      descending: sort.descending,
    }),
    [debouncedSearch, includeStaff, blockedBy, subscription, trial, sort],
  );

  const { state, setState, isFetching, isLoadingMore, hasMore, loadMore: handleLoadMore, reload } = usePaginatedList(
    (filters, page, signal) => listUsers({ ...filters, page, pageSize: DEFAULT_PAGE_SIZE }, signal),
    baseFilters,
  );
  // a card opened from the header search changed or deleted someone
  useEntityChanged("user", () => {
    reload();
    refreshStats();
  });

  const handleDeleted = (userId: number) =>
    setState((prev) =>
      prev.kind === "ready"
        ? { kind: "ready", items: prev.items.filter((u) => u.id !== userId), total: prev.total - 1 }
        : prev,
    );

  const handleUserUpdated = (updated: UserListItem) => {
    setState((prev) =>
      prev.kind === "ready"
        ? {
            kind: "ready",
            // block/unblock responses carry no subscription count
            items: prev.items.map((u) =>
              u.id === updated.id ? { ...updated, active_subscriptions: u.active_subscriptions } : u,
            ),
            total: prev.total,
          }
        : prev,
    );
    refreshStats();
  };

  const actions = useUserActions({
    onUpdated: handleUserUpdated,
    onDeleted: (user) => {
      handleDeleted(user.id);
      refreshStats();
    },
  });

  const toggleSort = (by: UserSort) =>
    setSort((prev) => ({ by, descending: prev.by === by ? !prev.descending : by !== "name" }));

  const sortHeader = (by: UserSort, label: string) => {
    const isActive = sort.by === by;
    const Arrow = sort.descending ? ArrowDown : ArrowUp;
    return (
      <button
        type="button"
        onClick={() => toggleSort(by)}
        className={`flex items-center gap-1 uppercase transition-colors hover:text-foreground ${
          isActive ? "text-foreground" : ""
        }`}
      >
        {label}
        {isActive && <Arrow className="size-3" />}
      </button>
    );
  };

  const channels = (user: UserListItem): { key: string; icon: LucideIcon }[] =>
    [
      user.telegram_id !== null && { key: "telegram", icon: Send },
      user.email && { key: "email", icon: Mail },
      user.login && { key: "login", icon: KeyRound },
    ].filter((channel): channel is { key: string; icon: LucideIcon } => Boolean(channel));

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {KPIS.map((value) => (
          <KpiTile
            key={value}
            label={t(`users.kpi.${value}`)}
            value={stats ? String(stats[KPI_STAT[value]]) : "—"}
            hint={
              value === "subscribed" || value === "blocked"
                ? stats && stats.total > 0
                  ? t("users.kpi.shareHint", {
                      percent: formatPercent(String(stats[value] / stats.total), i18n.language),
                    })
                  : undefined
                : t(`users.kpi.${value}Hint`)
            }
            trend={
              stats && value === "all"
                ? { delta: stats.total_growth, hint: t("users.kpi.totalTrend") }
                : stats && value === "new"
                  ? { delta: stats.new - stats.new_previous, hint: t("users.kpi.newTrend") }
                  : undefined
            }
          />
        ))}
      </div>

      <Card>
        <div className="flex flex-wrap items-end gap-3">
          <SearchField
            id="users-search"
            label={t("users.filters.search")}
            placeholder={t("users.filters.searchPlaceholder")}
            value={searchInput}
            onChange={setSearchInput}
          />
          <FilterSelect
            id="users-blocked-by"
            label={t("users.filters.blockedBy")}
            icon={Ban}
            value={blockedBy}
            onChange={(value) => setBlockedBy(value as BlockedBy | "")}
            options={[
              { value: "", label: t("users.filters.blockedByAll") },
              { value: "manual", label: t("users.filters.blockedByManual"), icon: BLOCKED_DOT },
              { value: "lists", label: t("users.filters.blockedByLists"), icon: LISTS_DOT },
            ]}
          />
          <FilterSelect
            id="users-subscription"
            label={t("users.filters.subscription")}
            icon={CreditCard}
            value={subscription}
            onChange={setSubscription}
            options={[
              { value: "", label: t("users.filters.subscriptionAll") },
              { value: "true", label: t("users.filters.subscriptionWith"), icon: YES_DOT },
              { value: "false", label: t("users.filters.subscriptionWithout"), icon: NO_DOT },
            ]}
          />
          <FilterSelect
            id="users-trial"
            label={t("users.filters.trial")}
            icon={Gift}
            value={trial}
            onChange={setTrial}
            options={[
              { value: "", label: t("users.filters.trialAll") },
              { value: "true", label: t("users.filters.trialAvailable"), icon: YES_DOT },
              { value: "false", label: t("users.filters.trialUsed"), icon: NO_DOT },
            ]}
          />
        </div>
      </Card>

      <Card className="relative">
        {state.kind === "ready" && isFetching && (
          <Loader2 className="absolute right-4 top-4 size-3.5 animate-spin text-muted-foreground" />
        )}
        {state.kind === "loading" && <Spinner size="page" />}
        {state.kind === "error" && (
          <ErrorState text={t("users.loadError")} size="page" />
        )}
        {state.kind === "ready" && state.items.length === 0 && <EmptyState text={t(hasFilters ? "users.noMatches" : "users.empty")} size="page" />}
        {state.kind === "ready" && state.items.length > 0 && (
          // overflow-y-hidden: overflow-x-auto alone makes y scrollable too, and the rows' rise-in (list-rows) would flash a scrollbar
          <div className="-mx-2 -my-1 overflow-x-auto overflow-y-hidden px-2 py-1">
            <div className="min-w-[860px]">
              <div
                className={`${ROW_GRID_CLASSNAME} ${LIST_HEAD_CLASS}`}
              >
                <span className="col-span-2">{sortHeader("name", t("users.columns.user"))}</span>
                {sortHeader("channels", t("users.columns.channels"))}
                {sortHeader("subscriptions", t("users.columns.subscriptions"))}
                {sortHeader("created_at", t("users.columns.registered"))}
                <span />
              </div>
              <div className={LIST_BODY_CLASS}>
                {state.items.map((user) => {
                  const isDeleted = Boolean(user.deleted_at);
                  const displayName = isDeleted ? t("users.deleted.name") : user.name;
                  // the per-user session endpoints reject yourself
                  const canViewSessions =
                    !isDeleted && user.id !== currentUserId && permissions.includes("USER_SESSIONS_VIEW");

                  const menuItems: ActionMenuItem[] = [
                    {
                      label: t("users.details.button"),
                      icon: Info,
                      onClick: () => setDetailsUser(user),
                    },
                  ];
                  if (canViewSessions) {
                    menuItems.push({
                      label: t("admins.details.tabs.sessions"),
                      icon: LaptopMinimal,
                      onClick: () => {
                        setDetailsTab("sessions");
                        setDetailsUser(user);
                      },
                    });
                  }
                  if (permissions.includes("EVENT_LOG_VIEW")) {
                    menuItems.push({
                      label: t("admins.details.tabs.events"),
                      icon: History,
                      onClick: () => {
                        setDetailsTab("events");
                        setDetailsUser(user);
                      },
                    });
                  }
                  const available = actions.available(user);
                  if (available.includes("promote")) {
                    menuItems.push({
                      label: t("admins.promote.button"),
                      icon: ShieldPlus,
                      onClick: () => actions.run("promote", user),
                    });
                  }
                  if (available.includes("bindTelegram")) {
                    menuItems.push({
                      label: t("users.telegram.action"),
                      icon: Send,
                      onClick: () => actions.run("bindTelegram", user),
                    });
                  }
                  if (available.includes("unblock")) {
                    menuItems.push({
                      label: t("users.unblock.button"),
                      icon: CircleCheck,
                      onClick: () => actions.run("unblock", user),
                    });
                  }
                  const dangerItems: ActionMenuItem[] = [];
                  if (available.includes("block")) {
                    dangerItems.push({
                      label: t("users.block.button"),
                      icon: Ban,
                      variant: "danger",
                      onClick: () => actions.run("block", user),
                    });
                  }
                  if (available.includes("merge")) {
                    dangerItems.push({
                      label: t("users.merge.action"),
                      icon: GitMerge,
                      variant: "danger",
                      onClick: () => actions.run("merge", user),
                    });
                  }
                  if (available.includes("delete")) {
                    dangerItems.push({
                      label: t("users.delete.button"),
                      icon: Trash2,
                      variant: "danger",
                      onClick: () => actions.run("delete", user),
                    });
                  }
                  menuItems.push(...dangerItems.map((item, index) => ({ ...item, separatorBefore: index === 0 })));

                  return (
                    <motion.div
                      key={user.id}
                      {...bounceTap(0.03)}
                      className={`${ROW_GRID_CLASSNAME} relative ${LIST_ROW_CLASS} hover:bg-white/[0.04] has-[[aria-expanded=true]]:z-20`}
                    >
                      {/* whole-row hit area; sits under the action menu (z-10) */}
                      <button
                        type="button"
                        onClick={() => setDetailsUser(user)}
                        className="absolute inset-0 cursor-pointer rounded-full"
                      />
                      <span
                        className={`flex size-9 items-center justify-center rounded-full text-[12.5px] font-bold ${getAvatarClassName(user, user.id === currentUserId)}`}
                      >
                        {isDeleted ? <Trash2 className="size-4" /> : initials(user.login ?? user.name)}
                      </span>
                      <span className="min-w-0">
                        <span className="flex min-w-0 items-center gap-2">
                          <span
                            className={`truncate text-[13.5px] font-medium ${isDeleted ? "text-muted-foreground" : "text-foreground"}`}
                          >
                            {displayName}
                          </span>
                          {user.role !== "USER" && (
                            <Badge tone={ROLE_BADGE_TONE[user.role]}>
                              {t(`roles.${user.role}`)}
                            </Badge>
                          )}
                        </span>
                        <span className="block truncate font-mono text-[12px] text-muted-foreground">
                          {userHandle(user)}
                        </span>
                      </span>
                      <span className="flex flex-wrap gap-1">
                        {channels(user).map(({ key, icon: Icon }) => (
                          <span
                            key={key}
                            className="flex size-6 items-center justify-center rounded-full bg-white/[0.06] text-muted-foreground"
                          >
                            <Icon className="size-3" />
                          </span>
                        ))}
                      </span>
                      <span className="flex items-center gap-1">
                        {subscriptionCounts(user).map(({ status, count }) => (
                          <Badge key={status} tone={SUBSCRIPTION_STATUS_BADGE_TONE[status]} shape="count">
                            {count}
                          </Badge>
                        ))}
                        {subscriptionCounts(user).length === 0 && (
                          <span className="text-[13.5px] text-muted-foreground">—</span>
                        )}
                      </span>
                      <span className="tabular-nums">
                        {user.created_at ? (
                          <>
                            <span className="block text-[13px] text-foreground">
                              {formatDate(user.created_at, i18n.language)}
                            </span>
                            <span className="block text-[11.5px] text-muted-foreground">
                              {formatRelative(user.created_at, i18n.language)}
                            </span>
                          </>
                        ) : (
                          <span className="text-[13px] text-muted-foreground">—</span>
                        )}
                      </span>
                      <span className="relative z-10 flex justify-end">
                        <ActionMenu items={menuItems} />
                      </span>
                    </motion.div>
                  );
                })}
              </div>
            </div>
          </div>
        )}
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
      </Card>

      {detailsUser && (
        <UserDetailsDialog
          user={detailsUser}
          initialTab={detailsTab}
          onChanged={handleUserUpdated}
          onDeleted={(user) => {
            handleDeleted(user.id);
            refreshStats();
          }}
          onClose={() => {
            setDetailsUser(null);
            setDetailsTab(undefined);
          }}
        />
      )}

      {actions.dialogs}
    </div>
  );
}
