import {
  AlertCircle,
  BarChart3,
  ChevronDown,
  Copy,
  Filter,
  Inbox,
  Link2,
  Loader2,
  Pencil,
  Plus,
  Trash2,
} from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { type AdLink, DEFAULT_PAGE_SIZE, deleteAdLink, listAdLinks } from "@entities/advertising/api";
import { useCurrentUser } from "@entities/user/use-current-user";
import { AdLinkCreateDialog } from "@features/ad-link-create/AdLinkCreateDialog";
import { AdLinkEditDialog } from "@features/ad-link-edit/AdLinkEditDialog";
import { AdLinkStatsDialog } from "@features/ad-link-stats/AdLinkStatsDialog";
import { getErrorMessage } from "@shared/api/http";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { toast } from "@shared/lib/toast";
import { ActionMenu, type ActionMenuItem } from "@shared/ui/ActionMenu";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { SelectDropdown } from "@shared/ui/SelectDropdown";
import { Spinner } from "@shared/ui/Spinner";

type LoadState = { kind: "loading" } | { kind: "error" } | { kind: "ready"; items: AdLink[]; total: number };

const FETCH_INDICATOR_DELAY_MS = 150;

export function AdvertisingPage() {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const [state, setState] = useState<LoadState>({ kind: "loading" });
  const [isFetching, setIsFetching] = useState(false);
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(1);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  // Bumped on every primary load; a load-more from before a filter change
  // discards its result instead of appending to an already-replaced list.
  const loadGenRef = useRef(0);
  const [editingLink, setEditingLink] = useState<AdLink | null>(null);
  const [statsLink, setStatsLink] = useState<AdLink | null>(null);
  const [pendingDelete, setPendingDelete] = useState<AdLink | null>(null);

  const currentUserState = useCurrentUser();
  const permissions =
    currentUserState.kind === "ready" ? currentUserState.data.effective_permissions : [];
  const canCreate = permissions.includes("AD_LINKS_CREATE");
  const canUpdate = permissions.includes("AD_LINKS_UPDATE");
  const canDelete = permissions.includes("AD_LINKS_DELETE");
  const canGenerateCode = permissions.includes("AD_LINKS_GENERATE_CODE");
  const canViewStats = permissions.includes("AD_LINKS_STATS_VIEW");
  const canViewUsers = permissions.includes("AD_LINKS_USERS_VIEW");

  const baseFilters = useMemo<{ isActive?: boolean }>(
    () => ({ isActive: statusFilter === "" ? undefined : statusFilter === "true" }),
    [statusFilter],
  );

  useEffect(() => {
    const controller = new AbortController();
    const showFetchingTimeout = setTimeout(() => {
      if (!controller.signal.aborted) setIsFetching(true);
    }, FETCH_INDICATOR_DELAY_MS);
    loadGenRef.current += 1;
    setPage(1);
    listAdLinks({ ...baseFilters, page: 1, pageSize: DEFAULT_PAGE_SIZE }, controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) setState({ kind: "ready", items: result.items, total: result.total });
      })
      .catch(() => {
        if (!controller.signal.aborted) setState((prev) => (prev.kind === "ready" ? prev : { kind: "error" }));
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
      const result = await listAdLinks({ ...baseFilters, page: nextPage, pageSize: DEFAULT_PAGE_SIZE });
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

  const handleSaved = (link: AdLink) => {
    if (state.kind !== "ready") return;
    const exists = state.items.some((item) => item.id === link.id);
    setState({
      kind: "ready",
      items: exists ? state.items.map((item) => (item.id === link.id ? link : item)) : [link, ...state.items],
      total: exists ? state.total : state.total + 1,
    });
  };

  const handleDelete = async (link: AdLink) => {
    try {
      await deleteAdLink(link.id);
      if (state.kind === "ready") {
        setState({
          kind: "ready",
          items: state.items.filter((item) => item.id !== link.id),
          total: state.total - 1,
        });
      }
    } catch (err) {
      toast.error(getErrorMessage(err, t("advertising.delete.error")));
    }
  };

  const handleCopy = (code: string) => {
    navigator.clipboard?.writeText(code).catch(() => {});
  };

  const hasMore = state.kind === "ready" && state.items.length < state.total;

  return (
    <div className="flex flex-col gap-4">
      <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex min-w-40 flex-1 flex-col gap-1.5">
            <label className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
              {t("advertising.filters.status")}
            </label>
            <SelectDropdown
              id="advertising-status"
              value={statusFilter}
              onChange={setStatusFilter}
              icon={Filter}
              placeholder={t("advertising.filters.statusAll")}
              options={[
                { value: "", label: t("advertising.filters.statusAll") },
                { value: "true", label: t("advertising.filters.statusActive") },
                { value: "false", label: t("advertising.filters.statusInactive") },
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
            <p className="text-sm">{t("advertising.loadError")}</p>
          </div>
        )}
        {state.kind === "ready" && (
          <>
            <div className="mb-3 flex justify-end">
              {canCreate && (
                <motion.button
                  type="button"
                  onClick={() => setIsCreateOpen(true)}
                  {...bounceTap(bounceStrength)}
                  className="flex items-center gap-1.5 rounded-full bg-accent px-4 py-2 text-[13px] font-semibold text-primary transition-colors hover:bg-primary/20"
                >
                  <Plus className="size-3.5" />
                  {t("advertising.create.button")}
                </motion.button>
              )}
            </div>

            {state.items.length === 0 && (
              <div className="flex flex-col items-center gap-2 py-12 text-muted-foreground">
                <Inbox className="size-5" />
                <p className="text-sm">{t("advertising.empty")}</p>
              </div>
            )}

            {state.items.length > 0 && (
              <>
                <div className="flex flex-col divide-y divide-border/50">
                  {state.items.map((link) => {
                    const menuItems: ActionMenuItem[] = [];
                    if (canViewStats) {
                      menuItems.push({
                        label: t("advertising.stats.button"),
                        icon: BarChart3,
                        onClick: () => setStatsLink(link),
                      });
                    }
                    if (canUpdate) {
                      menuItems.push({
                        label: t("advertising.edit.button"),
                        icon: Pencil,
                        onClick: () => setEditingLink(link),
                      });
                    }
                    if (canDelete) {
                      menuItems.push({
                        label: t("advertising.delete.button"),
                        icon: Trash2,
                        variant: "danger",
                        onClick: () => setPendingDelete(link),
                      });
                    }

                    return (
                      <div
                        key={link.id}
                        className="flex items-center justify-between gap-3 rounded-full px-3 py-2.5 [transition-property:background-color] duration-150 hover:bg-white/[0.04]"
                      >
                        <div className="flex min-w-0 items-center gap-3">
                          <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-white/[0.06] text-foreground">
                            <Link2 className="size-4" />
                          </div>
                          <div className="min-w-0">
                            <p className="truncate text-[13.5px] font-medium text-foreground">{link.name}</p>
                            <div className="flex items-center gap-1.5">
                              <p className="truncate font-mono text-[12px] text-muted-foreground">{link.code}</p>
                              <button
                                type="button"
                                onClick={() => handleCopy(link.code)}
                                aria-label={link.code}
                                className="text-muted-foreground transition-colors hover:text-foreground"
                              >
                                <Copy className="size-3" />
                              </button>
                            </div>
                          </div>
                        </div>

                        <div className="flex shrink-0 items-center gap-4">
                          <div className="text-right">
                            <p className="text-[11px] text-muted-foreground">{t("advertising.fields.cost")}</p>
                            <p className="text-[13px] font-medium text-foreground">
                              {link.cost} {link.cost_currency}
                            </p>
                          </div>
                          <span
                            className={`shrink-0 rounded-full border px-2 py-0.5 text-[10.5px] font-semibold uppercase tracking-wide ${
                              link.is_active
                                ? "border-success/30 bg-success/10 text-success"
                                : "border-border bg-white/[0.04] text-muted-foreground"
                            }`}
                          >
                            {link.is_active
                              ? t("advertising.filters.statusActive")
                              : t("advertising.filters.statusInactive")}
                          </span>
                          {menuItems.length > 0 && <ActionMenu items={menuItems} />}
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
                      aria-label={isLoadingMore ? t("advertising.pagination.loadingMore") : undefined}
                      {...bounceTap(bounceStrength)}
                      className="flex items-center gap-1.5 rounded-full border border-border px-4 py-2 text-sm text-foreground/90 transition-colors hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {isLoadingMore ? (
                        <Loader2 className="size-3.5 animate-spin" />
                      ) : (
                        <ChevronDown className="size-3.5" />
                      )}
                      {!isLoadingMore && t("advertising.pagination.loadMore")}
                    </motion.button>
                  </div>
                )}
              </>
            )}
          </>
        )}
      </div>

      {isCreateOpen && (
        <AdLinkCreateDialog
          canGenerateCode={canGenerateCode}
          onClose={() => setIsCreateOpen(false)}
          onSaved={handleSaved}
        />
      )}

      {editingLink && (
        <AdLinkEditDialog adLink={editingLink} onClose={() => setEditingLink(null)} onSaved={handleSaved} />
      )}

      {statsLink && (
        <AdLinkStatsDialog adLink={statsLink} canViewUsers={canViewUsers} onClose={() => setStatsLink(null)} />
      )}

      {pendingDelete && (
        <ConfirmDialog
          title={t("advertising.delete.button")}
          message={t("advertising.delete.confirm", { name: pendingDelete.name })}
          confirmLabel={t("advertising.delete.confirmButton")}
          cancelLabel={t("advertising.delete.cancelButton")}
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
