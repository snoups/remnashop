import { AlertCircle, ChevronDown, Filter, Inbox, Layers, Loader2, Pencil, Trash2 } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  DEFAULT_PAGE_SIZE,
  deleteSubscription,
  listSubscriptions,
  type SubscriptionListItem,
  type SubscriptionStatus,
} from "@entities/subscriptions/api";
import { useCurrentUser } from "@entities/user/use-current-user";
import { SubscriptionEditDialog } from "@features/subscription-edit/SubscriptionEditDialog";
import { getErrorMessage } from "@shared/api/http";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { toast } from "@shared/lib/toast";
import { ActionMenu, type ActionMenuItem } from "@shared/ui/ActionMenu";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { SelectDropdown } from "@shared/ui/SelectDropdown";
import { Spinner } from "@shared/ui/Spinner";

type LoadState =
  | { kind: "loading" }
  | { kind: "error" }
  | { kind: "ready"; items: SubscriptionListItem[]; total: number };

const STATUSES: SubscriptionStatus[] = ["ACTIVE", "LIMITED", "EXPIRED", "DISABLED", "DELETED"];
// Only surface the dimmed-loading state once a refetch has been in flight
// this long -- matches UsersPage's own debounce-flash guard.
const FETCH_INDICATOR_DELAY_MS = 150;

const STATUS_BADGE_CLASSNAME: Record<SubscriptionStatus, string> = {
  ACTIVE: "border-success/30 bg-success/10 text-success",
  LIMITED: "border-warning/30 bg-warning/10 text-warning",
  EXPIRED: "border-error/30 bg-error/10 text-error",
  DISABLED: "border-border bg-white/[0.04] text-muted-foreground",
  DELETED: "border-border bg-white/[0.04] text-muted-foreground",
};

function formatTraffic(gb: number, unlimitedLabel: string): string {
  return gb === 0 ? unlimitedLabel : `${gb} GB`;
}

function formatLimit(value: number, unlimitedLabel: string): string {
  return value === 0 ? unlimitedLabel : String(value);
}

function formatExpireDate(iso: string): string {
  return new Date(iso).toLocaleDateString();
}

export function SubscriptionsPage() {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const [state, setState] = useState<LoadState>({ kind: "loading" });
  const [isFetching, setIsFetching] = useState(false);
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  // Bumped on every primary load (mount, filter change); a load-more that
  // started under an older value discards its result instead of appending
  // stale rows to a list the effect has already replaced.
  const loadGenRef = useRef(0);
  const [editingSubscription, setEditingSubscription] = useState<SubscriptionListItem | null>(null);
  const [pendingDelete, setPendingDelete] = useState<SubscriptionListItem | null>(null);

  const currentUserState = useCurrentUser();
  const permissions =
    currentUserState.kind === "ready" ? currentUserState.data.effective_permissions : [];
  const canEdit = permissions.includes("SUBSCRIPTIONS_UPDATE");
  const canDelete = permissions.includes("SUBSCRIPTIONS_DELETE");

  const unlimitedLabel = t("subscriptions.unlimited");

  const baseFilters = useMemo<{ status?: SubscriptionStatus }>(
    () => ({ status: (status || undefined) as SubscriptionStatus | undefined }),
    [status],
  );

  useEffect(() => {
    const controller = new AbortController();
    loadGenRef.current += 1;
    const showFetchingTimeout = setTimeout(() => {
      if (!controller.signal.aborted) setIsFetching(true);
    }, FETCH_INDICATOR_DELAY_MS);
    setPage(1);
    listSubscriptions({ ...baseFilters, page: 1, pageSize: DEFAULT_PAGE_SIZE }, controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) {
          setState({ kind: "ready", items: result.items, total: result.total });
        }
      })
      .catch(() => {
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

  // Offset pagination + local optimistic edits (delete below) can drift a row
  // at a page boundary; acceptable for an admin list with infrequent deletes.
  // offset drift on boundary, switch to keyset if it bites.
  const handleLoadMore = async () => {
    const gen = loadGenRef.current;
    const nextPage = page + 1;
    setIsLoadingMore(true);
    try {
      const result = await listSubscriptions({ ...baseFilters, page: nextPage, pageSize: DEFAULT_PAGE_SIZE });
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

  const handleSaved = (updated: SubscriptionListItem) => {
    if (state.kind !== "ready") return;
    setState({
      kind: "ready",
      items: state.items.map((item) => (item.id === updated.id ? updated : item)),
      total: state.total,
    });
  };

  const handleDelete = async (subscription: SubscriptionListItem) => {
    try {
      await deleteSubscription(subscription.id);
      if (state.kind === "ready") {
        setState({
          kind: "ready",
          items: state.items.filter((item) => item.id !== subscription.id),
          total: state.total - 1,
        });
      }
    } catch (err) {
      toast.error(getErrorMessage(err, t("subscriptions.delete.error")));
    }
  };

  const hasMore = state.kind === "ready" && state.items.length < state.total;

  return (
    <div className="flex flex-col gap-4">
      <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex min-w-40 flex-1 flex-col gap-1.5">
            <label className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
              {t("subscriptions.filters.status")}
            </label>
            <SelectDropdown
              id="subscriptions-status"
              value={status}
              onChange={setStatus}
              icon={Filter}
              placeholder={t("subscriptions.filters.statusAll")}
              options={[
                { value: "", label: t("subscriptions.filters.statusAll") },
                ...STATUSES.map((s) => ({ value: s, label: t(`subscriptions.status.${s}`) })),
              ]}
            />
          </div>
        </div>
      </div>

      <div className="relative rounded-2xl border border-white/[0.08] bg-white/[0.03] p-4">
        {state.kind === "ready" && isFetching && (
          <Loader2 className="absolute right-4 top-4 size-3.5 animate-spin text-muted-foreground" />
        )}
        {state.kind === "loading" && <Spinner className="py-12" />}
        {state.kind === "error" && (
          <div className="flex flex-col items-center gap-2 py-12 text-error">
            <AlertCircle className="size-5" />
            <p className="text-sm">{t("subscriptions.loadError")}</p>
          </div>
        )}
        {state.kind === "ready" && (
          <>
            {state.items.length === 0 && (
              <div className="flex flex-col items-center gap-2 py-12 text-muted-foreground">
                <Inbox className="size-5" />
                <p className="text-sm">{t("subscriptions.empty")}</p>
              </div>
            )}
            {state.items.length > 0 && (
              <>
                <div className="flex flex-col divide-y divide-border/50">
                  {state.items.map((subscription) => {
                    const squadCount = subscription.internal_squads.length + (subscription.external_squad ? 1 : 0);

                    const menuItems: ActionMenuItem[] = [];
                    if (canEdit) {
                      menuItems.push({
                        label: t("subscriptions.edit.button"),
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
                        className="flex items-center justify-between gap-3 rounded-full px-3 py-2.5 [transition-property:background-color] duration-150 hover:bg-white/[0.04]"
                      >
                        <div className="flex min-w-0 items-center gap-3">
                          <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-white/[0.06] text-foreground">
                            <Layers className="size-4" />
                          </div>
                          <div className="min-w-0">
                            <div className="flex items-center gap-2">
                              <p className="truncate text-[13.5px] font-medium text-foreground">
                                {t("subscriptions.userLabel", { id: subscription.user_id })}
                              </p>
                              {subscription.is_trial && (
                                <span className="shrink-0 rounded-full border border-warning/30 bg-warning/10 px-2 py-0.5 text-[10.5px] font-semibold uppercase tracking-wide text-warning">
                                  {t("subscriptions.trial")}
                                </span>
                              )}
                              {subscription.tag && (
                                <span className="shrink-0 rounded-full border border-primary/40 bg-accent px-2 py-0.5 text-[10.5px] font-semibold uppercase tracking-wide text-primary">
                                  {subscription.tag}
                                </span>
                              )}
                            </div>
                            <p className="truncate font-mono text-[12px] text-muted-foreground">
                              #{subscription.id} &middot; {t("subscriptions.fields.squads", { count: squadCount })}
                            </p>
                          </div>
                        </div>

                        <div className="flex shrink-0 items-center gap-4">
                          <div className="text-right">
                            <p className="text-[11px] text-muted-foreground">{t("subscriptions.fields.traffic")}</p>
                            <p className="text-[13px] font-medium text-foreground">
                              {formatTraffic(subscription.effective_traffic_limit, unlimitedLabel)}
                            </p>
                          </div>
                          <div className="text-right">
                            <p className="text-[11px] text-muted-foreground">{t("subscriptions.fields.devices")}</p>
                            <p className="text-[13px] font-medium text-foreground">
                              {formatLimit(subscription.effective_device_limit, unlimitedLabel)}
                            </p>
                          </div>
                          <div className="text-right">
                            <p className="text-[11px] text-muted-foreground">{t("subscriptions.fields.expires")}</p>
                            <p className="text-[13px] font-medium text-foreground">
                              {formatExpireDate(subscription.expire_at)}
                            </p>
                          </div>
                          <span
                            className={`shrink-0 rounded-full border px-2 py-0.5 text-[10.5px] font-semibold uppercase tracking-wide ${STATUS_BADGE_CLASSNAME[subscription.status]}`}
                          >
                            {t(`subscriptions.status.${subscription.status}`)}
                          </span>
                          <ActionMenu items={menuItems} />
                        </div>
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
                      aria-label={isLoadingMore ? t("subscriptions.pagination.loadingMore") : undefined}
                      {...bounceTap(bounceStrength)}
                      className="flex items-center gap-1.5 rounded-full border border-border px-4 py-2 text-sm text-foreground/90 transition-colors hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {isLoadingMore ? (
                        <Loader2 className="size-3.5 animate-spin" />
                      ) : (
                        <ChevronDown className="size-3.5" />
                      )}
                      {!isLoadingMore && t("subscriptions.pagination.loadMore")}
                    </motion.button>
                  </div>
                )}
              </>
            )}
          </>
        )}
      </div>

      {editingSubscription && (
        <SubscriptionEditDialog
          subscription={editingSubscription}
          onClose={() => setEditingSubscription(null)}
          onSaved={handleSaved}
        />
      )}

      {pendingDelete && (
        <ConfirmDialog
          title={t("subscriptions.delete.button")}
          message={t("subscriptions.delete.confirm", { id: pendingDelete.id })}
          confirmLabel={t("subscriptions.delete.confirmButton")}
          cancelLabel={t("subscriptions.delete.cancelButton")}
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
