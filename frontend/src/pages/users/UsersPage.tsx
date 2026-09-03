import {
  AlertCircle,
  Ban,
  ChevronDown,
  Filter,
  Inbox,
  Info,
  LaptopMinimal,
  Loader2,
  Lock,
  Search,
  Trash2,
  Unlock,
} from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  DEFAULT_PAGE_SIZE,
  blockUser,
  deleteUser,
  listUsers,
  unblockAllUsers,
  unblockUser,
  type UserListFilters,
  type UserListItem,
} from "@entities/user/api";
import { deleteAdmin } from "@entities/admin/api";
import { UserDetailsDialog } from "@features/user-details/UserDetailsDialog";
import { UserSessionsDialog } from "@features/user-sessions/UserSessionsDialog";
import { getErrorMessage } from "@shared/api/http";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { useDebouncedValue } from "@shared/lib/use-debounced-value";
import { toast } from "@shared/lib/toast";
import { useCurrentUser } from "@entities/user/use-current-user";
import type { Role } from "@shared/types/rbac";
import { ActionMenu, type ActionMenuItem } from "@shared/ui/ActionMenu";
import { SelectDropdown } from "@shared/ui/SelectDropdown";

type LoadState =
  | { kind: "loading" }
  | { kind: "error" }
  | { kind: "ready"; items: UserListItem[]; total: number };

const ROLES: Role[] = ["USER", "ADMIN", "OWNER"];
const FILTER_DEBOUNCE_MS = 200;
const LOAD_MORE_STEP = 10;
// Only surface the dimmed-loading state once a refetch has been in flight
// this long -- most requests resolve well under it, so typing quickly no
// longer flashes the list dim/opaque on every keystroke pause.
const FETCH_INDICATOR_DELAY_MS = 150;

const ROLE_BADGE_CLASSNAME: Record<Role, string> = {
  USER: "border-border bg-white/[0.04] text-muted-foreground",
  ADMIN: "border-border bg-white/[0.06] text-foreground/80",
  OWNER: "border-primary/40 bg-accent text-primary",
  SYSTEM: "border-warning/30 bg-warning/10 text-warning",
};

function getContact(user: UserListItem): string {
  if (user.login) return user.login;
  if (user.username) return user.username;
  if (user.telegram_id !== null) return String(user.telegram_id);
  if (user.email) return user.email;
  return "—";
}

function getInitials(user: UserListItem): string {
  return (user.login ?? user.name).slice(0, 2).toUpperCase();
}

const fieldLabelClassName = "text-[11px] font-semibold uppercase tracking-wide text-muted-foreground";
const fieldClassName =
  "rounded-xl border border-border bg-input/60 py-2 text-sm text-foreground outline-none focus:border-primary";

export function UsersPage() {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const [state, setState] = useState<LoadState>({ kind: "loading" });
  const [isFetching, setIsFetching] = useState(false);
  const [searchInput, setSearchInput] = useState("");
  const [role, setRole] = useState("");
  const [isBlocked, setIsBlocked] = useState("");
  const [visibleCount, setVisibleCount] = useState(DEFAULT_PAGE_SIZE);
  const [isLoadingMore, setIsLoadingMore] = useState(false);

  const currentUserState = useCurrentUser();
  const permissions =
    currentUserState.kind === "ready" ? currentUserState.data.effective_permissions : [];
  const currentUserId = currentUserState.kind === "ready" ? currentUserState.data.id : null;
  const [sessionsUser, setSessionsUser] = useState<UserListItem | null>(null);
  const [detailsUser, setDetailsUser] = useState<UserListItem | null>(null);

  const debouncedSearch = useDebouncedValue(searchInput, FILTER_DEBOUNCE_MS);

  const baseFilters = useMemo<Omit<UserListFilters, "page" | "pageSize">>(
    () => ({
      search: debouncedSearch || undefined,
      role: (role || undefined) as Role | undefined,
      isBlocked: isBlocked === "" ? undefined : isBlocked === "true",
    }),
    [debouncedSearch, role, isBlocked],
  );

  useEffect(() => {
    let cancelled = false;
    const showFetchingTimeout = setTimeout(() => {
      if (!cancelled) setIsFetching(true);
    }, FETCH_INDICATOR_DELAY_MS);
    setVisibleCount(DEFAULT_PAGE_SIZE);
    listUsers({ ...baseFilters, page: 1, pageSize: DEFAULT_PAGE_SIZE })
      .then((result) => {
        if (!cancelled) {
          setState({ kind: "ready", items: result.items, total: result.total });
        }
      })
      .catch(() => {
        // keep showing whatever's already on screen; only surface the error
        // state when there's nothing else to show
        if (!cancelled) {
          setState((prev) => (prev.kind === "ready" ? prev : { kind: "error" }));
        }
      })
      .finally(() => {
        clearTimeout(showFetchingTimeout);
        if (!cancelled) setIsFetching(false);
      });
    return () => {
      cancelled = true;
      clearTimeout(showFetchingTimeout);
    };
  }, [baseFilters]);

  const handleLoadMore = async () => {
    const nextCount = visibleCount + LOAD_MORE_STEP;
    setIsLoadingMore(true);
    try {
      const result = await listUsers({ ...baseFilters, page: 1, pageSize: nextCount });
      setState({ kind: "ready", items: result.items, total: result.total });
      setVisibleCount(nextCount);
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
    if (!window.confirm(t("users.delete.confirm", { name: user.name }))) return;
    try {
      if (user.role === "ADMIN") {
        await deleteAdmin(user.id);
      } else {
        await deleteUser(user.id);
      }
      handleDeleted(user.id);
    } catch (err) {
      toast.error(getErrorMessage(err, t("users.delete.error")));
    }
  };

  const handleUserUpdated = (updated: UserListItem) => {
    if (state.kind !== "ready") return;
    setState({
      kind: "ready",
      items: state.items.map((u) => (u.id === updated.id ? updated : u)),
      total: state.total,
    });
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

  const handleUnblockAll = async () => {
    if (!window.confirm(t("users.unblockAll.confirm"))) return;
    try {
      const result = await unblockAllUsers();
      toast.success(t("users.unblockAll.success", { count: result.unblocked }));
      const refetched = await listUsers({ ...baseFilters, page: 1, pageSize: visibleCount });
      setState({ kind: "ready", items: refetched.items, total: refetched.total });
    } catch (err) {
      toast.error(getErrorMessage(err, t("users.unblockAll.error")));
    }
  };

  const hasMore = state.kind === "ready" && state.items.length < state.total;

  return (
    <div className="flex flex-col gap-4">
      {permissions.includes("USERS_UNBLOCK_ALL") && (
        <div className="flex justify-end">
          <motion.button
            type="button"
            onClick={() => void handleUnblockAll()}
            {...bounceTap(bounceStrength)}
            className="flex items-center gap-1.5 rounded-full border border-border px-3.5 py-2 text-[12.5px] font-semibold text-foreground/90 transition-colors hover:bg-white/5"
          >
            <Unlock className="size-3.5" />
            {t("users.unblockAll.button")}
          </motion.button>
        </div>
      )}

      <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex min-w-40 flex-1 flex-col gap-1.5">
            <label className={fieldLabelClassName}>{t("users.filters.search")}</label>
            <motion.div
              className="group relative"
              {...bounceTap(bounceStrength)}
            >
              <Search className="pointer-events-none absolute left-3 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground transition-colors group-not-focus-within:group-hover:text-foreground group-focus-within:text-primary" />
              <input
                id="users-search"
                type="text"
                value={searchInput}
                onChange={(event) => setSearchInput(event.target.value)}
                placeholder={t("users.filters.searchPlaceholder")}
                className={`${fieldClassName} w-full pl-9 pr-3`}
              />
            </motion.div>
          </div>

          <div className="flex min-w-40 flex-1 flex-col gap-1.5">
            <label className={fieldLabelClassName}>{t("users.filters.role")}</label>
            <SelectDropdown
              id="users-role"
              value={role}
              onChange={setRole}
              icon={Filter}
              placeholder={t("users.filters.roleAll")}
              options={[
                { value: "", label: t("users.filters.roleAll") },
                ...ROLES.map((r) => ({ value: r, label: t(`roles.${r}`) })),
              ]}
            />
          </div>

          <div className="flex min-w-40 flex-1 flex-col gap-1.5">
            <label className={fieldLabelClassName}>{t("users.filters.status")}</label>
            <SelectDropdown
              id="users-status"
              value={isBlocked}
              onChange={setIsBlocked}
              icon={Ban}
              placeholder={t("users.filters.statusAll")}
              options={[
                { value: "", label: t("users.filters.statusAll") },
                { value: "false", label: t("users.filters.statusActive") },
                { value: "true", label: t("users.filters.statusBlocked") },
              ]}
            />
          </div>
        </div>
      </div>

      <div className="relative rounded-2xl border border-white/[0.08] bg-white/[0.03] p-4">
        {state.kind === "ready" && isFetching && (
          <Loader2 className="absolute right-4 top-4 size-3.5 animate-spin text-muted-foreground" />
        )}
        {state.kind === "loading" && (
          <div className="flex flex-col items-center gap-2 py-12 text-muted-foreground">
            <Loader2 className="size-5 animate-spin" />
            <p className="text-sm">{t("users.loading")}</p>
          </div>
        )}
        {state.kind === "error" && (
          <div className="flex flex-col items-center gap-2 py-12 text-error">
            <AlertCircle className="size-5" />
            <p className="text-sm">{t("users.loadError")}</p>
          </div>
        )}
        {state.kind === "ready" && (
          <>
            {state.items.length === 0 && (
              <div className="flex flex-col items-center gap-2 py-12 text-muted-foreground">
                <Inbox className="size-5" />
                <p className="text-sm">{t("users.empty")}</p>
              </div>
            )}
            {state.items.length > 0 && (
              <>
                <div className="flex flex-col divide-y divide-border/50">
                  {state.items.map((user) => {
                    const canDelete =
                      user.id !== currentUserId &&
                      ((user.role === "ADMIN" && permissions.includes("ADMINS_MANAGE")) ||
                        (user.role === "USER" && permissions.includes("USERS_DELETE")));
                    const canViewSessions = permissions.includes("USER_SESSIONS_VIEW");

                    const menuItems: ActionMenuItem[] = [
                      {
                        label: t("users.details.button"),
                        icon: Info,
                        onClick: () => setDetailsUser(user),
                      },
                    ];
                    if (canViewSessions) {
                      menuItems.push({
                        label: t("sessions.title"),
                        icon: LaptopMinimal,
                        onClick: () => setSessionsUser(user),
                      });
                    }
                    if (permissions.includes(user.is_blocked ? "USERS_UNBLOCK" : "USERS_BLOCK")) {
                      menuItems.push({
                        label: user.is_blocked ? t("users.unblock.button") : t("users.block.button"),
                        icon: user.is_blocked ? Unlock : Lock,
                        onClick: () => void (user.is_blocked ? handleUnblock(user) : handleBlock(user)),
                      });
                    }
                    if (canDelete) {
                      menuItems.push({
                        label: t("users.delete.button"),
                        icon: Trash2,
                        variant: "danger",
                        onClick: () => void handleDelete(user),
                      });
                    }

                    return (
                      <div
                        key={user.id}
                        className="flex items-center justify-between gap-3 rounded-full px-3 py-2.5 [transition-property:background-color] duration-150 hover:bg-white/[0.04]"
                      >
                        <div className="flex min-w-0 items-center gap-3">
                          <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-white/[0.06] text-[12.5px] font-bold text-foreground">
                            {getInitials(user)}
                          </div>
                          <div className="min-w-0">
                            <div className="flex items-center gap-2">
                              <p className="truncate text-[13.5px] font-medium text-foreground">
                                {user.name}
                              </p>
                              {user.role !== "USER" && (
                                <span
                                  className={`shrink-0 rounded-full border px-2 py-0.5 text-[10.5px] font-semibold uppercase tracking-wide ${ROLE_BADGE_CLASSNAME[user.role]}`}
                                >
                                  {t(`roles.${user.role}`)}
                                </span>
                              )}
                              {user.is_blocked && (
                                <span className="shrink-0 rounded-full border border-error/30 bg-error/10 px-2 py-0.5 text-[10.5px] font-semibold uppercase tracking-wide text-error">
                                  {t("users.blocked")}
                                </span>
                              )}
                            </div>
                            <p className="truncate font-mono text-[12px] text-muted-foreground">
                              {getContact(user)}
                            </p>
                          </div>
                        </div>

                        <ActionMenu items={menuItems} />
                      </div>
                    );
                  })}
                </div>
                {hasMore && (
                  <div className="mt-4 flex justify-center">
                    <motion.button
                      type="button"
                      onClick={() => void handleLoadMore()}
                      disabled={isLoadingMore}
                      {...bounceTap(bounceStrength)}
                      className="flex items-center gap-1.5 rounded-full border border-border px-4 py-2 text-sm text-foreground/90 transition-colors hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {isLoadingMore ? (
                        <Loader2 className="size-3.5 animate-spin" />
                      ) : (
                        <ChevronDown className="size-3.5" />
                      )}
                      {isLoadingMore
                        ? t("users.pagination.loadingMore")
                        : t("users.pagination.loadMore")}
                    </motion.button>
                  </div>
                )}
              </>
            )}
          </>
        )}
      </div>

      {sessionsUser && (
        <UserSessionsDialog
          userId={sessionsUser.id}
          userName={sessionsUser.name}
          onClose={() => setSessionsUser(null)}
        />
      )}

      {detailsUser && <UserDetailsDialog user={detailsUser} onClose={() => setDetailsUser(null)} />}
    </div>
  );
}
