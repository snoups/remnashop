import { ArrowDown, ArrowUp, Ban, Bot, CircleCheck, Gift, GitMerge, History, Info, KeyRound, LaptopMinimal, Layers, Mail, Send, ShieldPlus, Trash2, type LucideIcon, Unlink, User, UserMinus, Users } from "lucide-react";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  DEFAULT_PAGE_SIZE,
  getUserListStats,
  listUsers,
  type UserListFilters,
  type UserBase,
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
import { LoadGate, LoadGateHold } from "@shared/lib/load-gate";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { usePaginatedList } from "@shared/lib/use-paginated-list";
import { formatPercent } from "@shared/lib/format";
import { formatDate, formatRelative } from "@shared/lib/relative-time";
import { useUrlSearch } from "@shared/lib/use-url-search";
import { useDebouncedValue } from "@shared/lib/use-debounced-value";
import { initials } from "@shared/lib/initials";
import { userContacts, userName } from "@entities/user/display";
import { useCurrentUser, usePermissions } from "@entities/user/use-current-user";
import { ActionMenu, type ActionMenuItem } from "@shared/ui/ActionMenu";
import { Badge } from "@shared/ui/Badge";
import { AnimatedHeight } from "@shared/ui/glass/AnimatedHeight";
import { EmptyState, ErrorState } from "@shared/ui/glass/EmptyState";
import { KpiTile } from "@shared/ui/KpiTile";
import { LoadMoreButton } from "@shared/ui/LoadMoreButton";
import { SearchField } from "@shared/ui/SearchField";
import { SelectDropdown } from "@shared/ui/SelectDropdown";
import { dotIcon } from "@shared/ui/option-icons";
import { RefetchSpinner, Spinner } from "@shared/ui/Spinner";
import { GLASS_LIST_HEAD_CLASS, GLASS_LIST_ROW_CLASS, LIST_BODY_CLASS, LIST_SCROLL_X_CLASS, PAGE_CLASS, PAGE_SCROLL_UNDER_BAR_CLASS, PAGE_TOOLBAR_CLASS, PAGE_TOOLBAR_SEARCH_CLASS } from "@shared/ui/classes";
import { Pressable } from "@shared/ui/Pressable";

type Kpi = "all" | "subscribed" | "churned" | "blocked";

const KPIS: Kpi[] = ["all", "subscribed", "churned", "blocked"];
const FILTER_DEBOUNCE_MS = 200;

const ROW_GRID_CLASSNAME =
  "grid grid-cols-[32px_minmax(0,1fr)_100px_90px_130px_32px] items-center gap-3";

const YES_DOT = dotIcon("bg-success");
const NO_DOT = dotIcon("bg-muted-foreground");
const BLOCKED_DOT = dotIcon("bg-error");
const LISTS_DOT = dotIcon("bg-warning");
const DELETED_DOT = dotIcon("bg-muted-foreground");
// the account-state filter's last choice: anonymized accounts, which the list leaves out otherwise
const DELETED_FILTER = "deleted";

const KPI_STAT: Record<Kpi, keyof UserListStats> = {
  all: "total",
  subscribed: "subscribed",
  churned: "churned",
  blocked: "blocked",
};
const KPI_ICON: Record<Kpi, LucideIcon> = {
  all: Users,
  subscribed: Layers,
  churned: UserMinus,
  blocked: Ban,
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

export function UsersPage() {
  const { t, i18n } = useTranslation();
  const [searchInput, setSearchInput] = useUrlSearch();
  const [blockedBy, setBlockedBy] = useState<BlockedBy | typeof DELETED_FILTER | "">("");
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
      blockedBy: blockedBy && blockedBy !== DELETED_FILTER ? blockedBy : undefined,
      deleted: blockedBy === DELETED_FILTER ? "only" : undefined,
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

  const handleUserUpdated = (updated: UserBase) => {
    setState((prev) =>
      prev.kind === "ready"
        ? {
            kind: "ready",
            items: prev.items.map((u) => (u.id === updated.id ? { ...u, ...updated } : u)),
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
      <Pressable
        type="button"
        onClick={() => toggleSort(by)}
        // negative margins: the pill gives the ripple room without shifting the label off its column
        className={`-mx-2 -my-1 flex items-center gap-1 rounded-full px-2 py-1 uppercase transition-colors hover:text-foreground ${
          isActive ? "text-foreground" : ""
        }`}
      >
        {label}
        {isActive && <Arrow className="size-3" />}
      </Pressable>
    );
  };

  const channels = (user: UserListItem): { key: string; icon: LucideIcon }[] =>
    [
      user.telegram_id !== null && { key: "telegram", icon: Bot },
      user.email && { key: "email", icon: Mail },
      user.login && { key: "login", icon: KeyRound },
    ].filter((channel): channel is { key: string; icon: LucideIcon } => Boolean(channel));

  return (
    <div data-fills-main className={PAGE_CLASS}>
      <div className={PAGE_TOOLBAR_CLASS}>
        <div className={PAGE_TOOLBAR_SEARCH_CLASS}>
          <SearchField
            id="users-search"
            placeholder={t("users.filters.searchPlaceholder")}
            value={searchInput}
            onChange={setSearchInput}
          />
        </div>
        <div className="min-w-40 flex-1 md:w-56 md:min-w-0 md:flex-none">
          <SelectDropdown
            id="users-blocked-by"
            value={blockedBy}
            onChange={(value) => setBlockedBy(value as BlockedBy | typeof DELETED_FILTER | "")}
            icon={Ban}
            size="compact"
            glassPopover
            placeholder={t("users.filters.blockedByAll")}
            options={[
              { value: "", label: t("users.filters.blockedByAll"), icon: Ban },
              { value: "manual", label: t("users.filters.blockedByManual"), icon: BLOCKED_DOT },
              { value: "lists", label: t("users.filters.blockedByLists"), icon: LISTS_DOT },
              { value: DELETED_FILTER, label: t("users.filters.deleted"), icon: DELETED_DOT },
            ]}
          />
        </div>
        <div className="min-w-40 flex-1 md:w-56 md:min-w-0 md:flex-none">
          <SelectDropdown
            id="users-subscription"
            value={subscription}
            onChange={setSubscription}
            icon={Layers}
            size="compact"
            glassPopover
            placeholder={t("users.filters.subscriptionAll")}
            options={[
              { value: "", label: t("users.filters.subscriptionAll"), icon: Layers },
              { value: "true", label: t("users.filters.subscriptionWith"), icon: YES_DOT },
              { value: "false", label: t("users.filters.subscriptionWithout"), icon: NO_DOT },
            ]}
          />
        </div>
        <div className="min-w-40 flex-1 md:w-56 md:min-w-0 md:flex-none">
          <SelectDropdown
            id="users-trial"
            value={trial}
            onChange={setTrial}
            icon={Gift}
            size="compact"
            glassPopover
            placeholder={t("users.filters.trialAll")}
            options={[
              { value: "", label: t("users.filters.trialAll"), icon: Gift },
              { value: "true", label: t("users.filters.trialAvailable"), icon: YES_DOT },
              { value: "false", label: t("users.filters.trialUsed"), icon: NO_DOT },
            ]}
          />
        </div>
      </div>

      <div className={`${PAGE_SCROLL_UNDER_BAR_CLASS} flex flex-col gap-5`}>
      <LoadGate>
      <LoadGateHold isLoading={state.kind === "loading" || statsState.kind === "loading"} />
      <div className="flex flex-col gap-5">
      <div className="grid shrink-0 grid-cols-2 gap-5 lg:grid-cols-4">
        {KPIS.map((value) => (
          <KpiTile
            panel
            key={value}
            icon={KPI_ICON[value]}
            label={t(`users.kpi.${value}`)}
            value={stats ? String(stats[KPI_STAT[value]]) : "—"}
            hint={
              value !== "all"
                ? stats && stats.total > 0
                  ? t("users.kpi.shareHint", {
                      percent: formatPercent(String(stats[KPI_STAT[value]] / stats.total), i18n.language),
                    })
                  : undefined
                : t("users.kpi.allHint")
            }
            trend={
              stats && value === "all"
                ? { delta: stats.total_growth, hint: t("users.kpi.totalTrend") }
                : undefined
            }
          />
        ))}
      </div>

      <div className="glass-panel relative shrink-0 rounded-3xl p-4">
        {state.kind === "ready" && isFetching && <RefetchSpinner />}
        <AnimatedHeight>
        {state.kind === "loading" && <Spinner size="page" />}
        {state.kind === "error" && (
          <ErrorState text={t("common.loadError")} size="page" />
        )}
        {state.kind === "ready" && state.items.length === 0 && <EmptyState text={t(hasFilters ? "users.noMatches" : "users.empty")} size="page" />}
        {state.kind === "ready" && state.items.length > 0 && (
          <div className={LIST_SCROLL_X_CLASS}>
            <div className="min-w-[720px]">
              <div
                className={`${ROW_GRID_CLASSNAME} ${GLASS_LIST_HEAD_CLASS}`}
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
                  const displayName = userName(user, t);
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
                  if (available.includes("unbindTelegram")) {
                    menuItems.push({
                      label: t("users.telegram.unbind"),
                      icon: Unlink,
                      onClick: () => actions.run("unbindTelegram", user),
                    });
                  }
                  if (available.includes("unblock")) {
                    menuItems.push({
                      label: t("users.unblock.action"),
                      icon: CircleCheck,
                      onClick: () => actions.run("unblock", user),
                    });
                  }
                  const dangerItems: ActionMenuItem[] = [];
                  if (available.includes("merge")) {
                    dangerItems.push({
                      label: t("users.merge.action"),
                      icon: GitMerge,
                      variant: "danger",
                      onClick: () => actions.run("merge", user),
                    });
                  }
                  if (available.includes("block")) {
                    dangerItems.push({
                      label: t("users.block.action"),
                      icon: Ban,
                      variant: "danger",
                      onClick: () => actions.run("block", user),
                    });
                  }
                  if (available.includes("delete")) {
                    dangerItems.push({
                      label: t("common.delete"),
                      icon: Trash2,
                      variant: "danger",
                      onClick: () => actions.run("delete", user),
                    });
                  }
                  menuItems.push(...dangerItems.map((item, index) => ({ ...item, separatorBefore: index === 0 })));

                  return (
                    <div
                      key={user.id}
                      className={`${ROW_GRID_CLASSNAME} relative ${GLASS_LIST_ROW_CLASS} hover:bg-white/[0.04] has-[[aria-expanded=true]]:z-20`}
                    >
                      {/* whole-row hit area; sits under the action menu (z-10) */}
                      <Pressable
                        type="button"
                        onClick={() => setDetailsUser(user)}
                        className="absolute inset-0 cursor-pointer rounded-full" />
                      <span
                        className={`flex size-8 items-center justify-center rounded-full text-xs font-bold ${getAvatarClassName(user, user.id === currentUserId)}`}
                      >
                        {isDeleted ? (
                          <Trash2 className="size-4" />
                        ) : user.login || user.name ? (
                          initials(user.login ?? user.name)
                        ) : (
                          <User className="size-4" />
                        )}
                      </span>
                      <span className="min-w-0">
                        <span className="flex min-w-0 items-center gap-2">
                          <span
                            className={`truncate text-sm font-medium ${isDeleted ? "text-muted-foreground" : "text-foreground"}`}
                          >
                            {displayName}
                          </span>
                          <span className="shrink-0 font-mono text-xs text-muted-foreground">
                            #{user.id}
                          </span>
                          {user.role !== "USER" && (
                            <Badge tone={ROLE_BADGE_TONE[user.role]}>
                              {t(`roles.${user.role}`)}
                            </Badge>
                          )}
                        </span>
                        <span className="block truncate text-xs text-muted-foreground">
                          {userContacts(user, t)}
                        </span>
                      </span>
                      <span className="flex flex-wrap gap-1">
                        {channels(user).map(({ key, icon: Icon }) => (
                          <span
                            key={key}
                            className="flex size-6 items-center justify-center rounded-full bg-white/[0.06] text-muted-foreground"
                          >
                            <Icon className="size-3.5" />
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
                          <span className="text-sm text-muted-foreground">—</span>
                        )}
                      </span>
                      <span className="tabular-nums">
                        {user.created_at ? (
                          <>
                            <span className="block text-sm text-foreground">
                              {formatDate(user.created_at, i18n.language)}
                            </span>
                            <span className="block text-xs text-muted-foreground">
                              {formatRelative(user.created_at, i18n.language)}
                            </span>
                          </>
                        ) : (
                          <span className="text-sm text-muted-foreground">—</span>
                        )}
                      </span>
                      <span className="relative z-10 flex justify-end">
                        <ActionMenu items={menuItems} />
                      </span>
                    </div>
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
        </AnimatedHeight>
      </div>
      </div>
      </LoadGate>
      </div>

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
