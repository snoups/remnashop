import {
  AlertCircle,
  Check,
  ChevronDown,
  Copy,
  Filter,
  Inbox,
  Link2,
  Loader2,
  Megaphone,
  Pause,
  Pencil,
  Play,
  Plus,
  Trash2,
  Users,
} from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useMemo, useRef, useState } from "react";
import type { ComponentType, ReactNode } from "react";
import { useTranslation } from "react-i18next";

import {
  type AdLink,
  AD_LINK_START_PREFIX,
  type AdvertisingSummary,
  DEFAULT_PAGE_SIZE,
  deleteAdLink,
  getAdvertisingSummary,
  listAdLinks,
  updateAdLink,
} from "@entities/advertising/api";
import { formatMoney, formatPercent, roiClassName } from "@entities/advertising/format";
import { useCurrentUser } from "@entities/user/use-current-user";
import { AdLinkCreateDialog } from "@features/ad-link-create/AdLinkCreateDialog";
import { AdLinkEditDialog } from "@features/ad-link-edit/AdLinkEditDialog";
import { AdLinkStatsPanel } from "@features/ad-link-stats/AdLinkStatsPanel";
import { AdLinkUsersDialog } from "@features/ad-link-stats/AdLinkUsersDialog";
import { getErrorMessage } from "@shared/api/http";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { toast } from "@shared/lib/toast";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { PeriodPills } from "@shared/ui/PeriodPills";
import type { PeriodDays } from "@shared/ui/PeriodToggle";
import { SelectDropdown } from "@shared/ui/SelectDropdown";
import { Spinner } from "@shared/ui/Spinner";

type LoadState = { kind: "loading" } | { kind: "error" } | { kind: "ready"; items: AdLink[]; total: number };

const FETCH_INDICATOR_DELAY_MS = 150;
const COPIED_FEEDBACK_MS = 1500;

const STATS_GRID_CLASSNAME =
  "grid grid-cols-[36px_minmax(0,1fr)_84px_72px_88px_104px_76px_92px_16px] items-center gap-3";
const PLAIN_GRID_CLASSNAME = "grid grid-cols-[36px_minmax(0,1fr)_104px_92px_16px] items-center gap-3";

const cardClassName = "rounded-2xl border border-white/[0.08] bg-white/[0.03]";
const columnLabelClassName = "text-[11px] font-semibold uppercase tracking-wide text-muted-foreground";

export function AdvertisingPage() {
  const { t, i18n } = useTranslation();
  const bounceStrength = useBounceStrength();
  const [state, setState] = useState<LoadState>({ kind: "loading" });
  const [isFetching, setIsFetching] = useState(false);
  const [statusFilter, setStatusFilter] = useState("");
  const [period, setPeriod] = useState<PeriodDays>(30);
  const [page, setPage] = useState(1);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  // Bumped on every primary load; a load-more from before a filter change
  // discards its result instead of appending to an already-replaced list.
  const loadGenRef = useRef(0);
  const [summary, setSummary] = useState<AdvertisingSummary | null>(null);
  // bumped after create/edit/delete so the metrics catch up with the list
  const [summaryVersion, setSummaryVersion] = useState(0);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [copiedId, setCopiedId] = useState<number | null>(null);
  const [editingLink, setEditingLink] = useState<AdLink | null>(null);
  const [usersLink, setUsersLink] = useState<AdLink | null>(null);
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

  const isActive = statusFilter === "" ? undefined : statusFilter === "true";
  const createdFrom = useMemo(
    () => (period ? new Date(Date.now() - period * 86_400_000).toISOString() : undefined),
    [period],
  );

  useEffect(() => {
    const controller = new AbortController();
    const showFetchingTimeout = setTimeout(() => {
      if (!controller.signal.aborted) setIsFetching(true);
    }, FETCH_INDICATOR_DELAY_MS);
    loadGenRef.current += 1;
    setPage(1);
    listAdLinks({ isActive, page: 1, pageSize: DEFAULT_PAGE_SIZE }, controller.signal)
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
  }, [isActive]);

  useEffect(() => {
    if (!canViewStats) return;
    const controller = new AbortController();
    getAdvertisingSummary({ isActive, createdFrom }, controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) setSummary(result);
      })
      .catch(() => {
        // metrics are secondary; the list stays usable with dashes in their place
      });
    return () => controller.abort();
  }, [canViewStats, isActive, createdFrom, summaryVersion]);

  const metricsById = useMemo(
    () => new Map(summary?.links.map((link) => [link.ad_link_id, link]) ?? []),
    [summary],
  );

  // Offset pagination + local optimistic edits (delete below) can drift a row
  // at a page boundary; acceptable for an admin list with infrequent deletes.
  // offset drift on boundary, switch to keyset if it bites.
  const handleLoadMore = async () => {
    const gen = loadGenRef.current;
    const nextPage = page + 1;
    setIsLoadingMore(true);
    try {
      const result = await listAdLinks({ isActive, page: nextPage, pageSize: DEFAULT_PAGE_SIZE });
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
    setSummaryVersion((version) => version + 1);
    setState((prev) => {
      if (prev.kind !== "ready") return prev;
      const exists = prev.items.some((item) => item.id === link.id);
      return {
        kind: "ready",
        items: exists ? prev.items.map((item) => (item.id === link.id ? link : item)) : [link, ...prev.items],
        total: exists ? prev.total : prev.total + 1,
      };
    });
  };

  const handleDelete = async (link: AdLink) => {
    try {
      await deleteAdLink(link.id);
      setSummaryVersion((version) => version + 1);
      setState((prev) =>
        prev.kind === "ready"
          ? { kind: "ready", items: prev.items.filter((item) => item.id !== link.id), total: prev.total - 1 }
          : prev,
      );
    } catch (err) {
      toast.error(getErrorMessage(err, t("advertising.delete.error")));
    }
  };

  const handleToggleActive = async (link: AdLink) => {
    try {
      handleSaved(await updateAdLink(link.id, { is_active: !link.is_active }));
    } catch (err) {
      toast.error(getErrorMessage(err, t("advertising.edit.error")));
    }
  };

  const handleCopy = (link: AdLink) => {
    navigator.clipboard
      ?.writeText(`?start=${AD_LINK_START_PREFIX}${link.code}`)
      .then(() => {
        setCopiedId(link.id);
        setTimeout(() => setCopiedId((id) => (id === link.id ? null : id)), COPIED_FEEDBACK_MS);
      })
      .catch(() => {});
  };

  const hasMore = state.kind === "ready" && state.items.length < state.total;
  const gridClassName = canViewStats ? STATS_GRID_CLASSNAME : PLAIN_GRID_CLASSNAME;
  const none = t("advertising.stats.none");
  const money = (amount: string) => formatMoney(amount, summary?.report_currency ?? "", i18n.language);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="w-48">
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
        <div className="flex flex-wrap items-center gap-3">
          {canViewStats && (
            <PeriodPills value={period} onChange={setPeriod} ariaLabel={t("advertising.filters.period")} />
          )}
          {canCreate && (
            <motion.button
              type="button"
              onClick={() => setIsCreateOpen(true)}
              {...bounceTap(bounceStrength)}
              className="flex h-10 items-center gap-1.5 rounded-full bg-primary px-4 text-[13px] font-semibold text-primary-foreground transition-colors hover:bg-primary-hover"
            >
              <Plus className="size-3.5" />
              {t("advertising.create.button")}
            </motion.button>
          )}
        </div>
      </div>

      {canViewStats && (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <KpiTile
            label={t("advertising.stats.attributions")}
            value={summary ? String(summary.attributions_count) : none}
            hint={
              summary
                ? t("advertising.stats.channelSplit", {
                    bot: summary.attributions_by_channel.BOT ?? 0,
                    web: summary.attributions_by_channel.WEBCABINET ?? 0,
                  })
                : undefined
            }
          />
          <KpiTile
            label={t("advertising.stats.paidCount")}
            value={summary ? String(summary.paid_count) : none}
            hint={
              summary
                ? `${t("advertising.stats.conversionRate")} ${formatPercent(summary.conversion_rate, i18n.language)}`
                : undefined
            }
          />
          <KpiTile
            label={t("advertising.stats.cost")}
            value={summary ? money(summary.cost) : none}
            hint={summary?.cpa != null ? `${t("advertising.stats.cpa")} ${money(summary.cpa)}` : undefined}
          />
          <KpiTile
            highlighted
            label={t("advertising.stats.revenue")}
            value={summary ? money(summary.revenue) : none}
            hint={
              summary?.roi != null ? (
                <>
                  {t("advertising.stats.roi")}{" "}
                  <span className={`font-semibold ${roiClassName(summary.roi)}`}>
                    {formatPercent(summary.roi, i18n.language, true)}
                  </span>
                </>
              ) : undefined
            }
          />
        </div>
      )}

      <div className={`relative p-4 ${cardClassName}`}>
        <div className="flex items-center gap-2.5">
          <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] text-foreground backdrop-blur-md">
            <Megaphone className="size-4" />
          </div>
          <div className="min-w-0 flex-1">
            <h2 className="text-sm font-bold text-foreground">{t("advertising.title")}</h2>
            <p className="mt-0.5 text-[12.5px] text-muted-foreground">{t("advertising.description")}</p>
          </div>
          {state.kind === "ready" && isFetching ? (
            <Loader2 className="size-3.5 animate-spin text-muted-foreground" />
          ) : (
            state.kind === "ready" && (
              <span className="text-[12px] tabular-nums text-muted-foreground">
                {t("advertising.count", { count: state.total })}
              </span>
            )
          )}
        </div>

        <div className="-mx-4 mt-4 border-t border-white/[0.07]" />

        {state.kind === "loading" && <Spinner className="py-12" />}
        {state.kind === "error" && (
          <div className="flex flex-col items-center gap-2 py-12 text-error">
            <AlertCircle className="size-5" />
            <p className="text-sm">{t("advertising.loadError")}</p>
          </div>
        )}
        {state.kind === "ready" && state.items.length === 0 && (
          <div className="flex flex-col items-center gap-2 py-12 text-muted-foreground">
            <Inbox className="size-5" />
            <p className="text-sm">{t("advertising.empty")}</p>
          </div>
        )}
        {state.kind === "ready" && state.items.length > 0 && (
          <>
            <div className={`${gridClassName} mb-1 border-b border-border px-3 pb-2.5 pt-3.5 ${columnLabelClassName}`}>
              <span className="col-span-2">{t("advertising.columns.link")}</span>
              {canViewStats && (
                <>
                  <span className="text-right">{t("advertising.stats.attributions")}</span>
                  <span className="text-right">{t("advertising.columns.paid")}</span>
                  <span className="text-right">{t("advertising.stats.conversionRate")}</span>
                </>
              )}
              <span className="text-right">{t("advertising.stats.cost")}</span>
              {canViewStats && <span className="text-right">{t("advertising.stats.roi")}</span>}
              <span>{t("advertising.columns.status")}</span>
              <span />
            </div>

            <div className="flex flex-col divide-y divide-border/50">
              {state.items.map((link) => {
                const metrics = metricsById.get(link.id);
                const isExpanded = expandedId === link.id;
                const conversion =
                  metrics && metrics.attributions_count > 0 ? metrics.paid_count / metrics.attributions_count : null;

                return (
                  <div key={link.id} className="flex flex-col">
                    <motion.button
                      type="button"
                      aria-expanded={isExpanded}
                      onClick={() => setExpandedId(isExpanded ? null : link.id)}
                      {...bounceTap(bounceStrength, 0.03)}
                      className={`${gridClassName} w-full rounded-full px-3 py-2.5 text-left [transition-property:background-color] duration-150 hover:bg-white/[0.04] ${
                        isExpanded ? "bg-white/[0.04]" : ""
                      }`}
                    >
                      <span
                        aria-hidden
                        className={`flex size-9 items-center justify-center rounded-full ${
                          link.is_active ? "bg-accent text-primary" : "bg-white/[0.06] text-muted-foreground"
                        }`}
                      >
                        <Link2 className="size-4" />
                      </span>
                      <span className="min-w-0">
                        <span className="block truncate text-[13.5px] font-medium text-foreground">{link.name}</span>
                        <span className="block truncate font-mono text-[12px] text-muted-foreground">{link.code}</span>
                      </span>
                      {canViewStats && (
                        <>
                          <span className="text-right text-[13.5px] font-semibold tabular-nums text-foreground">
                            {metrics?.attributions_count ?? none}
                          </span>
                          <span className="text-right text-[13.5px] tabular-nums text-foreground">
                            {metrics?.paid_count ?? none}
                          </span>
                          <span className="flex flex-col items-end gap-1">
                            <span className="text-[13px] tabular-nums text-foreground">
                              {conversion !== null ? formatPercent(String(conversion), i18n.language) : none}
                            </span>
                            <span className="h-[3px] w-14 overflow-hidden rounded-full bg-white/[0.07]">
                              <span
                                className="block h-full rounded-full bg-primary"
                                style={{ width: `${(conversion ?? 0) * 100}%` }}
                              />
                            </span>
                          </span>
                        </>
                      )}
                      <span className="text-right text-[13px] tabular-nums text-foreground">
                        {formatMoney(link.cost, link.cost_currency, i18n.language)}
                      </span>
                      {canViewStats && (
                        <span
                          className={`text-right text-[13.5px] font-semibold tabular-nums ${roiClassName(metrics?.roi ?? null)}`}
                        >
                          {metrics?.roi != null ? formatPercent(metrics.roi, i18n.language, true) : none}
                        </span>
                      )}
                      <span>
                        <span
                          className={`rounded-full border px-2 py-0.5 text-[10.5px] font-semibold uppercase tracking-wide ${
                            link.is_active
                              ? "border-success/30 bg-success/10 text-success"
                              : "border-border bg-white/[0.04] text-muted-foreground"
                          }`}
                        >
                          {link.is_active ? t("advertising.status.active") : t("advertising.status.paused")}
                        </span>
                      </span>
                      <ChevronDown
                        className={`size-4 text-muted-foreground transition-transform ${isExpanded ? "rotate-180" : ""}`}
                      />
                    </motion.button>

                    {isExpanded && (
                      <div className="flex flex-col gap-3.5 pb-4 pl-3 pr-3 pt-2 md:pl-[60px]">
                        <div className="flex flex-col gap-1">
                          <span className="text-sm font-medium text-foreground/80">{t("advertising.startParam")}</span>
                          <div className="flex items-center justify-between gap-2 rounded-xl border border-border bg-input/60 py-1.5 pl-3 pr-1.5">
                            <span className="truncate font-mono text-[13px] text-foreground">
                              ?start={AD_LINK_START_PREFIX}
                              {link.code}
                            </span>
                            <button
                              type="button"
                              onClick={() => handleCopy(link)}
                              aria-label={t("advertising.copyStartParam")}
                              className="flex size-7 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-white/[0.08] hover:text-foreground"
                            >
                              {copiedId === link.id ? (
                                <Check className="size-3.5 text-success" />
                              ) : (
                                <Copy className="size-3.5" />
                              )}
                            </button>
                          </div>
                          <span className="text-[12px] text-muted-foreground">{t("advertising.startParamHint")}</span>
                        </div>

                        {canViewStats && (
                          <AdLinkStatsPanel
                            key={`${link.id}-${period}`}
                            adLink={link}
                            periodDays={period}
                            createdFrom={createdFrom}
                          />
                        )}

                        {link.note && <p className="text-[12.5px] text-muted-foreground">{link.note}</p>}

                        <div className="flex flex-wrap gap-2">
                          {canViewUsers && (
                            <PanelButton icon={Users} variant="accent" onClick={() => setUsersLink(link)}>
                              {t("advertising.stats.usersTitle")}
                            </PanelButton>
                          )}
                          {canUpdate && (
                            <>
                              <PanelButton icon={Pencil} onClick={() => setEditingLink(link)}>
                                {t("advertising.edit.button")}
                              </PanelButton>
                              <PanelButton
                                icon={link.is_active ? Pause : Play}
                                onClick={() => void handleToggleActive(link)}
                              >
                                {link.is_active ? t("advertising.pause") : t("advertising.resume")}
                              </PanelButton>
                            </>
                          )}
                          {canDelete && (
                            <PanelButton icon={Trash2} variant="danger" onClick={() => setPendingDelete(link)}>
                              {t("advertising.delete.button")}
                            </PanelButton>
                          )}
                        </div>
                      </div>
                    )}
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
                  {isLoadingMore ? <Loader2 className="size-3.5 animate-spin" /> : <ChevronDown className="size-3.5" />}
                  {!isLoadingMore && t("advertising.pagination.loadMore")}
                </motion.button>
              </div>
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

      {usersLink && <AdLinkUsersDialog adLink={usersLink} onClose={() => setUsersLink(null)} />}

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

function KpiTile({
  label,
  value,
  hint,
  highlighted = false,
}: {
  label: string;
  value: string;
  hint?: ReactNode;
  highlighted?: boolean;
}) {
  return (
    <div
      className={`flex flex-col gap-1.5 rounded-2xl border px-[18px] py-4 ${
        highlighted ? "border-primary/25 bg-accent/60" : "border-white/[0.08] bg-white/[0.03]"
      }`}
    >
      <span
        className={`text-[11px] font-semibold uppercase tracking-wide ${
          highlighted ? "text-accent-foreground" : "text-muted-foreground"
        }`}
      >
        {label}
      </span>
      <span className="text-[26px] font-bold tabular-nums tracking-tight text-foreground">{value}</span>
      <span className="min-h-[18px] text-[12px] tabular-nums text-muted-foreground">{hint}</span>
    </div>
  );
}

function PanelButton({
  icon: Icon,
  variant = "default",
  onClick,
  children,
}: {
  icon: ComponentType<{ className?: string }>;
  variant?: "default" | "accent" | "danger";
  onClick: () => void;
  children: ReactNode;
}) {
  const bounceStrength = useBounceStrength();
  const variantClassName = {
    default: "bg-white/[0.06] text-foreground hover:bg-white/[0.1]",
    accent: "bg-accent text-primary hover:bg-primary/20",
    danger: "text-error hover:bg-error/10 sm:ml-auto",
  }[variant];

  return (
    <motion.button
      type="button"
      onClick={onClick}
      {...bounceTap(bounceStrength)}
      className={`flex items-center gap-1.5 rounded-full px-4 py-2 text-sm font-medium transition-colors ${variantClassName}`}
    >
      <Icon className="size-3.5" />
      {children}
    </motion.button>
  );
}
