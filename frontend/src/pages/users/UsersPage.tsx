import {
  AlertCircle,
  Ban,
  CircleCheck,
  CreditCard,
  ArrowDown,
  ArrowUp,
  Gift,
  Info,
  KeyRound,
  LaptopMinimal,
  Loader2,
  Mail,
  Send,
  Trash2,
  type LucideIcon,
} from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useMemo, useRef, useState, type ComponentType } from "react";
import { useTranslation } from "react-i18next";
import { useLocation, useNavigate } from "react-router-dom";

import {
  DEFAULT_PAGE_SIZE,
  blockUser,
  deleteUser,
  getUserListStats,
  getUser,
  listUsers,
  unblockUser,
  type UserListFilters,
  type UserListItem,
  type BlockedBy,
  type DeletedFilter,
  type UserListStats,
  type UserSort,
  type UsersLocationState,
} from "@entities/user/api";
import { deleteAdmin } from "@entities/admin/api";
import { ROLE_BADGE_TONE } from "@entities/admin/display";
import { UserDetailsDialog, type UserDetailsFollowUp } from "@features/user-details/UserDetailsDialog";
import { UserReferralsDialog } from "@features/user-referrals/UserReferralsDialog";
import { UserSessionsDialog } from "@features/user-sessions/UserSessionsDialog";
import { getErrorMessage } from "@shared/api/http";
import { formatPercent } from "@shared/lib/format";
import { bounceTap } from "@shared/lib/bounceState";
import { formatDate, formatRelative } from "@shared/lib/relative-time";
import { useUrlSearch } from "@shared/lib/use-url-search";
import { useDebouncedValue } from "@shared/lib/use-debounced-value";
import { toast } from "@shared/lib/toast";
import { useCurrentUser } from "@entities/user/use-current-user";
import { ActionMenu, type ActionMenuItem } from "@shared/ui/ActionMenu";
import { Badge } from "@shared/ui/Badge";
import { Card } from "@shared/ui/Card";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { EmptyState } from "@shared/ui/EmptyState";
import { KpiTile } from "@shared/ui/KpiTile";
import { LoadMoreButton } from "@shared/ui/LoadMoreButton";
import { SearchField } from "@shared/ui/SearchField";
import { SelectDropdown, type SelectOption } from "@shared/ui/SelectDropdown";
import { dotIcon } from "@shared/ui/optionIcons";
import { Spinner } from "@shared/ui/Spinner";
import { EYEBROW_CLASS, LIST_BODY_CLASS, LIST_HEAD_CLASS, LIST_ROW_CLASS } from "@shared/ui/classes";

type LoadState =
  | { kind: "loading" }
  | { kind: "error" }
  | { kind: "ready"; items: UserListItem[]; total: number };

type Kpi = "all" | "new" | "subscribed" | "blocked";

const KPIS: Kpi[] = ["all", "new", "subscribed", "blocked"];
const FILTER_DEBOUNCE_MS = 200;
// Only surface the dimmed-loading state once a refetch has been in flight
// this long -- most requests resolve well under it, so typing quickly no
// longer flashes the list dim/opaque on every keystroke pause.
const FETCH_INDICATOR_DELAY_MS = 150;

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

function getHandle(user: UserListItem): string {
  if (user.deleted_at) return `#${user.id}`;
  const telegram = [user.username ? `@${user.username}` : null, user.telegram_id !== null ? `ID ${user.telegram_id}` : null]
    .filter(Boolean)
    .join(" · ");
  return telegram || user.email || user.login || "—";
}

function getInitials(user: UserListItem): string {
  return (user.login ?? user.name).slice(0, 2).toUpperCase();
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
  const [state, setState] = useState<LoadState>({ kind: "loading" });
  const [isFetching, setIsFetching] = useState(false);
  const [searchInput, setSearchInput] = useUrlSearch();
  const location = useLocation();
  const [blockedBy, setBlockedBy] = useState<BlockedBy | "">("");
  // deleted accounts stay hidden, except for a handoff to one's card, which has to find it
  const [deleted] = useState<DeletedFilter | undefined>(() =>
    (location.state as UsersLocationState | null)?.deleted ? "include" : undefined,
  );
  const [subscription, setSubscription] = useState("");
  const [trial, setTrial] = useState("");
  const [sort, setSort] = useState<{ by: UserSort; descending: boolean }>({ by: "created_at", descending: true });
  const [stats, setStats] = useState<UserListStats | null>(null);
  const [statsToken, setStatsToken] = useState(0);
  const [page, setPage] = useState(1);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  // Bumped on every primary load (mount, filter change); a
  // load-more that started under an older value discards its result rather
  // than appending stale rows to a list the effect has already replaced.
  const loadGenRef = useRef(0);

  const currentUserState = useCurrentUser();
  const permissions =
    currentUserState.kind === "ready" ? currentUserState.data.effective_permissions : [];
  const currentUserId = currentUserState.kind === "ready" ? currentUserState.data.id : null;
  // staff rows are only listable with ADMINS_MANAGE (see ListUsersUseCase)
  const includeStaff = permissions.includes("ADMINS_MANAGE");
  const [sessionsUser, setSessionsUser] = useState<UserListItem | null>(null);
  const [detailsUser, setDetailsUser] = useState<UserListItem | null>(null);
  const [referralsUser, setReferralsUser] = useState<UserListItem | null>(null);
  const [pendingDelete, setPendingDelete] = useState<UserListItem | null>(null);
  const [pendingBlockAdmin, setPendingBlockAdmin] = useState<UserListItem | null>(null);
  // cancelling a delete/admin block started from the details dialog reopens it
  const [confirmFromDetails, setConfirmFromDetails] = useState(false);

  const debouncedSearch = useDebouncedValue(searchInput, FILTER_DEBOUNCE_MS);
  const navigate = useNavigate();
  const openUserIdRef = useRef((location.state as UsersLocationState | null)?.userId);

  // drop the handoff once consumed so a reload or back doesn't reopen the dialog
  useEffect(() => {
    if (detailsUser && location.state) navigate({ search: location.search }, { replace: true, state: null });
  }, [detailsUser, location.state, location.search, navigate]);

  useEffect(() => {
    const userId = openUserIdRef.current;
    if (userId === undefined) return;
    openUserIdRef.current = undefined;
    const controller = new AbortController();
    getUser(userId, controller.signal)
      .then(setDetailsUser)
      .catch(() => {});
    return () => controller.abort();
  }, []);

  const refreshStats = () => setStatsToken((token) => token + 1);

  useEffect(() => {
    const controller = new AbortController();
    getUserListStats(includeStaff, controller.signal)
      .then(setStats)
      .catch(() => {});
    return () => controller.abort();
  }, [includeStaff, statsToken]);

  const baseFilters = useMemo<Omit<UserListFilters, "page" | "pageSize">>(
    () => ({
      search: debouncedSearch || undefined,
      includeStaff,
      blockedBy: blockedBy || undefined,
      deleted,
      hasSubscription: parseTriState(subscription),
      isTrialAvailable: parseTriState(trial),
      sort: sort.by,
      descending: sort.descending,
    }),
    [debouncedSearch, includeStaff, blockedBy, subscription, trial, deleted, sort],
  );

  useEffect(() => {
    const controller = new AbortController();
    const showFetchingTimeout = setTimeout(() => {
      if (!controller.signal.aborted) setIsFetching(true);
    }, FETCH_INDICATOR_DELAY_MS);
    loadGenRef.current += 1;
    setPage(1);
    listUsers({ ...baseFilters, page: 1, pageSize: DEFAULT_PAGE_SIZE }, controller.signal)
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

  // Offset pagination + local optimistic edits (block/delete below) can drift
  // a row at a page boundary; acceptable for an admin list with infrequent
  // deletes. offset drift on boundary, switch to keyset if it bites.
  const handleLoadMore = async () => {
    const gen = loadGenRef.current;
    const nextPage = page + 1;
    setIsLoadingMore(true);
    try {
      const result = await listUsers({ ...baseFilters, page: nextPage, pageSize: DEFAULT_PAGE_SIZE });
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

  const handleDeleted = (userId: number) => {
    if (state.kind !== "ready") return;
    setState({
      kind: "ready",
      items: state.items.filter((u) => u.id !== userId),
      total: state.total - 1,
    });
  };

  const handleDelete = async (user: UserListItem) => {
    try {
      if (user.role === "ADMIN") {
        await deleteAdmin(user.id);
      } else {
        await deleteUser(user.id);
      }
      handleDeleted(user.id);
      refreshStats();
    } catch (err) {
      toast.error(getErrorMessage(err, t("users.delete.error")));
    }
  };

  const handleUserUpdated = (updated: UserListItem) => {
    if (state.kind !== "ready") return;
    setState({
      kind: "ready",
      // block/unblock responses carry no subscription count
      items: state.items.map((u) =>
        u.id === updated.id ? { ...updated, active_subscriptions: u.active_subscriptions } : u,
      ),
      total: state.total,
    });
    refreshStats();
  };

  const handleBlock = async (user: UserListItem) => {
    try {
      const updated = await blockUser(user.id);
      handleUserUpdated(updated);
    } catch (err) {
      toast.error(getErrorMessage(err, t("users.block.error")));
    }
  };

  const handleUnblock = async (user: UserListItem) => {
    try {
      const updated = await unblockUser(user.id);
      handleUserUpdated(updated);
    } catch (err) {
      toast.error(getErrorMessage(err, t("users.unblock.error")));
    }
  };

  const canDelete = (user: UserListItem) =>
    user.id !== currentUserId &&
    ((user.role === "ADMIN" && permissions.includes("ADMINS_MANAGE")) ||
      (user.role === "USER" && permissions.includes("USERS_DELETE")));

  const getFollowUps = (user: UserListItem): UserDetailsFollowUp[] => {
    // a deleted account is read-only
    if (user.deleted_at) return [];
    return [
      ...(permissions.includes(user.is_blocked ? "USERS_UNBLOCK" : "USERS_BLOCK")
        ? [user.is_blocked ? ("unblock" as const) : ("block" as const)]
        : []),
      ...(canDelete(user) ? ["delete" as const] : []),
    ];
  };

  // blocking an admin also demotes them and drops their sessions -- confirm first
  const requestBlock = (user: UserListItem, fromDetails: boolean) => {
    if (user.role !== "ADMIN") {
      void handleBlock(user);
      return;
    }
    setConfirmFromDetails(fromDetails);
    setPendingBlockAdmin(user);
  };

  const handleFollowUp = (user: UserListItem, followUp?: UserDetailsFollowUp) => {
    if (followUp === "block") requestBlock(user, true);
    if (followUp === "unblock") void handleUnblock(user);
    if (followUp === "delete") {
      setConfirmFromDetails(true);
      setPendingDelete(user);
    }
  };

  const toggleSort = (by: UserSort) =>
    setSort((prev) => ({ by, descending: prev.by === by ? !prev.descending : by !== "name" }));

  const hasMore = state.kind === "ready" && state.items.length < state.total;

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
          <div className="flex flex-col items-center gap-2 py-12 text-error">
            <AlertCircle className="size-5" />
            <p className="text-sm">{t("users.loadError")}</p>
          </div>
        )}
        {state.kind === "ready" && state.items.length === 0 && <EmptyState text={t("users.empty")} size="page" />}
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
                  const canViewSessions = !isDeleted && permissions.includes("USER_SESSIONS_VIEW");

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
                      onClick: () => setSessionsUser(user),
                    });
                  }
                  if (!isDeleted && permissions.includes("REFERRALS_VIEW")) {
                    menuItems.push({
                      label: t("referrals.stats.button"),
                      icon: Gift,
                      onClick: () => setReferralsUser(user),
                    });
                  }
                  if (!isDeleted && permissions.includes(user.is_blocked ? "USERS_UNBLOCK" : "USERS_BLOCK")) {
                    menuItems.push({
                      label: user.is_blocked ? t("users.unblock.button") : t("users.block.button"),
                      icon: user.is_blocked ? CircleCheck : Ban,
                      onClick: () => (user.is_blocked ? void handleUnblock(user) : requestBlock(user, false)),
                    });
                  }
                  if (!isDeleted && canDelete(user)) {
                    menuItems.push({
                      label: t("users.delete.button"),
                      icon: Trash2,
                      variant: "danger",
                      onClick: () => {
                        setConfirmFromDetails(false);
                        setPendingDelete(user);
                      },
                    });
                  }

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
                        {isDeleted ? <Trash2 className="size-4" /> : getInitials(user)}
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
                          {getHandle(user)}
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
                      <span>
                        {user.active_subscriptions ? (
                          <Badge tone="success">{user.active_subscriptions}</Badge>
                        ) : (
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

      {sessionsUser && (
        <UserSessionsDialog
          userId={sessionsUser.id}
          userName={sessionsUser.name}
          onClose={() => setSessionsUser(null)}
        />
      )}

      {detailsUser && (
        <UserDetailsDialog
          user={detailsUser}
          followUps={getFollowUps(detailsUser)}
          onClose={(followUp) => {
            handleFollowUp(detailsUser, followUp);
            setDetailsUser(null);
          }}
        />
      )}

      {referralsUser && (
        <UserReferralsDialog
          userId={referralsUser.id}
          userName={referralsUser.name}
          username={referralsUser.username}
          onClose={() => setReferralsUser(null)}
        />
      )}

      {pendingDelete && (
        <ConfirmDialog
          title={t("users.delete.confirmTitle")}
          message={t("users.delete.confirm", { name: pendingDelete.name })}
          confirmLabel={t("users.delete.confirmButton")}
          cancelLabel={t("users.delete.cancelButton")}
          danger
          onConfirm={() => {
            void handleDelete(pendingDelete);
            setPendingDelete(null);
          }}
          onCancel={() => {
            if (confirmFromDetails) setDetailsUser(pendingDelete);
            setPendingDelete(null);
          }}
        />
      )}

      {pendingBlockAdmin && (
        <ConfirmDialog
          title={t("users.blockAdmin.title")}
          message={t("users.blockAdmin.confirm", { name: pendingBlockAdmin.name })}
          confirmLabel={t("users.blockAdmin.confirmButton")}
          cancelLabel={t("users.blockAdmin.cancelButton")}
          danger
          onConfirm={() => {
            void handleBlock(pendingBlockAdmin);
            setPendingBlockAdmin(null);
          }}
          onCancel={() => {
            if (confirmFromDetails) setDetailsUser(pendingBlockAdmin);
            setPendingBlockAdmin(null);
          }}
        />
      )}

    </div>
  );
}
