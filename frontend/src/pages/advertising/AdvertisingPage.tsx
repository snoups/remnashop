import { Banknote, CalendarRange, ChevronRight, Filter, Link2, Plus, ShoppingCart, UserPlus, Wallet } from "lucide-react";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  type AdLink,
  type AdvertisingSummary,
  DEFAULT_PAGE_SIZE,
  getAdvertisingSummary,
  listAdLinks,
} from "@entities/advertising/api";
import { roiClassName } from "@entities/advertising/format";
import { usePermissions } from "@entities/user/use-current-user";
import { AdLinkCreateDialog } from "@features/ad-link-create/AdLinkCreateDialog";
import { AdLinkDetailsDialog } from "@features/ad-link-details/AdLinkDetailsDialog";
import { DAY_MS, previousWindow, PERIOD_DAYS, type PeriodDays } from "@shared/lib/period";
import { LoadGate, LoadGateHold } from "@shared/lib/load-gate";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { usePaginatedList } from "@shared/lib/use-paginated-list";
import { formatMoney, formatPercent } from "@shared/lib/format";
import { CellText } from "@shared/ui/CellText";
import { AnimatedHeight } from "@shared/ui/glass/AnimatedHeight";
import { EmptyState, ErrorState } from "@shared/ui/glass/EmptyState";
import { IconCircle } from "@shared/ui/glass/IconCircle";
import { LoadMoreButton } from "@shared/ui/LoadMoreButton";
import { KpiTile, type KpiTrend } from "@shared/ui/KpiTile";
import { dotIcon } from "@shared/ui/option-icons";
import { SelectDropdown } from "@shared/ui/SelectDropdown";
import { RefetchSpinner, Spinner } from "@shared/ui/Spinner";
import { Button } from "@shared/ui/Button";
import { Badge } from "@shared/ui/Badge";
import { GLASS_LIST_HEAD_CLASS, LIST_BODY_CLASS, LIST_SCROLL_X_CLASS, PAGE_CLASS, PAGE_SCROLL_UNDER_BAR_CLASS, PAGE_TOOLBAR_CLASS } from "@shared/ui/classes";
import { ListRow } from "@shared/ui/ListRow";

const STATS_GRID_CLASSNAME =
  "grid grid-cols-[32px_minmax(0,1fr)_88px_80px_104px_104px_80px_104px_16px] items-center gap-3";
const PLAIN_GRID_CLASSNAME = "grid grid-cols-[32px_minmax(0,1fr)_104px_104px_16px] items-center gap-3";

// mirrors AdLinkRepository.list_paginated: active first, then newest
function compareAdLinks(a: AdLink, b: AdLink): number {
  return (
    Number(b.is_active) - Number(a.is_active) ||
    (b.created_at ?? "").localeCompare(a.created_at ?? "") ||
    b.id - a.id
  );
}

export function AdvertisingPage() {
  const { t, i18n } = useTranslation();
  const [statusFilter, setStatusFilter] = useState("");
  const [period, setPeriod] = useState<PeriodDays>(0);
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  // an id, not the row: the dialog then follows edits/pause made from inside it
  const [detailsId, setDetailsId] = useState<number | null>(null);

  const permissions = usePermissions();
  const canCreate = permissions.includes("AD_LINKS_CREATE");
  const canUpdate = permissions.includes("AD_LINKS_UPDATE");
  const canDelete = permissions.includes("AD_LINKS_DELETE");
  const canGenerateCode = permissions.includes("AD_LINKS_GENERATE_CODE");
  const canViewStats = permissions.includes("AD_LINKS_STATS_VIEW");
  const canViewSummary = permissions.includes("AD_LINKS_SUMMARY_VIEW");
  const canViewUsers = permissions.includes("AD_LINKS_USERS_VIEW");
  const canShare = permissions.includes("AD_LINKS_SHARE_VIEW");

  const isActive = statusFilter === "" ? undefined : statusFilter === "true";
  const createdFrom = useMemo(
    () => (period ? new Date(Date.now() - period * DAY_MS).toISOString() : undefined),
    [period],
  );

  const { state, setState, isFetching, isLoadingMore, hasMore, loadMore: handleLoadMore } = usePaginatedList(
    (active, page, signal) => listAdLinks({ isActive: active, page, pageSize: DEFAULT_PAGE_SIZE }, signal),
    isActive,
  );

  const [summaryState, reloadSummary] = useAsyncResource(
    (signal) => (canViewSummary ? getAdvertisingSummary({ isActive, createdFrom }, signal) : Promise.resolve(null)),
    { deps: [canViewSummary, isActive, createdFrom], keepData: true },
  );
  const [compareState, reloadCompare] = useAsyncResource(
    (signal) =>
      canViewSummary ? getAdvertisingSummary({ isActive, ...previousWindow(period) }, signal) : Promise.resolve(null),
    { deps: [canViewSummary, isActive, period] },
  );
  const summary = summaryState.kind === "ready" ? summaryState.data : null;
  const compareSummary = compareState.kind === "ready" ? compareState.data : null;
  // after create/edit/delete, so the metrics catch up with the list
  const reloadSummaries = () => {
    reloadSummary();
    reloadCompare();
  };

  const metricsById = useMemo(
    () => new Map(summary?.links.map((link) => [link.ad_link_id, link]) ?? []),
    [summary],
  );

  const matchesFilter = (link: AdLink) => isActive === undefined || link.is_active === isActive;

  const handleSaved = (link: AdLink) => {
    reloadSummaries();
    setState((prev) => {
      if (prev.kind !== "ready") return prev;
      const exists = prev.items.some((item) => item.id === link.id);
      if (!exists && !matchesFilter(link)) return prev;
      const items = exists ? prev.items.map((item) => (item.id === link.id ? link : item)) : [link, ...prev.items];
      return {
        kind: "ready",
        items: items.sort(compareAdLinks),
        total: exists ? prev.total : prev.total + 1,
      };
    });
  };

  // a link paused or resumed in the dialog stays put until it closes, so the dialog doesn't vanish
  const dropUnmatched = () =>
    setState((prev) => {
      if (prev.kind !== "ready") return prev;
      const items = prev.items.filter(matchesFilter);
      return { kind: "ready", items, total: prev.total - (prev.items.length - items.length) };
    });

  const handleDeleted = (link: AdLink) => {
    reloadSummaries();
    setState((prev) =>
      prev.kind === "ready"
        ? { kind: "ready", items: prev.items.filter((item) => item.id !== link.id), total: prev.total - 1 }
        : prev,
    );
  };

  const gridClassName = canViewSummary ? STATS_GRID_CLASSNAME : PLAIN_GRID_CLASSNAME;
  const none = t("common.none");
  const money = (amount: string) => formatMoney(amount, summary?.report_currency ?? "", i18n.language);
  const trendHint = period ? t("advertising.stats.periodTrend", { days: period }) : t("advertising.stats.totalTrend");
  const countTrend = (pick: (s: AdvertisingSummary) => number): KpiTrend | undefined =>
    summary && compareSummary ? { delta: pick(summary) - pick(compareSummary), hint: trendHint } : undefined;
  const revenueTrend = ((): KpiTrend | undefined => {
    const base = Number(compareSummary?.revenue);
    if (!summary || !(base > 0)) return undefined;
    const delta = Number(summary.revenue) / base - 1;
    return { delta, text: formatPercent(String(Math.abs(delta)), i18n.language), hint: trendHint };
  })();
  const detailsLink = state.kind === "ready" ? state.items.find((item) => item.id === detailsId) : undefined;

  return (
    <div data-fills-main className={PAGE_CLASS}>
      <div className={PAGE_TOOLBAR_CLASS}>
        <div className="min-w-40 flex-1 md:min-w-0">
          <SelectDropdown
            id="advertising-status"
            value={statusFilter}
            onChange={setStatusFilter}
            icon={Filter}
            size="compact"
            glassPopover
            placeholder={t("advertising.filters.statusAll")}
            options={[
              { value: "", label: t("advertising.filters.statusAll"), icon: Filter },
              { value: "true", label: t("advertising.filters.statusActive"), icon: dotIcon("bg-success") },
              { value: "false", label: t("advertising.filters.statusInactive"), icon: dotIcon("bg-muted-foreground") },
            ]}
          />
        </div>
        {canViewSummary && (
          <div className="min-w-40 flex-1 md:min-w-0">
            <SelectDropdown
              id="advertising-period"
              value={String(period)}
              onChange={(value) => setPeriod(Number(value) as PeriodDays)}
              icon={CalendarRange}
              size="compact"
              glassPopover
              placeholder={t("dashboard.periodAll")}
              options={PERIOD_DAYS.map((days) => ({
                value: String(days),
                label: days === 0 ? t("dashboard.periodAll") : t("dashboard.periodDays", { count: days }),
                icon: CalendarRange,
              }))}
            />
          </div>
        )}
        {canCreate && (
          <Button variant="glassAccent" type="button" onClick={() => setIsCreateOpen(true)} className="ml-auto">
            <Plus className="size-4" />
            {t("advertising.create.button")}
          </Button>
        )}
      </div>

      <div className={`${PAGE_SCROLL_UNDER_BAR_CLASS} flex flex-col gap-5`}>
      <LoadGate>
      <LoadGateHold isLoading={state.kind === "loading" || summaryState.kind === "loading"} />
      <div className="flex flex-col gap-5">
      {canViewSummary && (
        <div className="grid shrink-0 grid-cols-2 gap-5 lg:grid-cols-4">
          <KpiTile
            panel
            icon={UserPlus}
            label={t("advertising.stats.attributions")}
            value={summary ? String(summary.attributions_count) : none}
            trend={countTrend((s) => s.attributions_count)}
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
            panel
            icon={ShoppingCart}
            label={t("advertising.stats.paidCount")}
            value={summary ? String(summary.paid_count) : none}
            trend={countTrend((s) => s.paid_count)}
            hint={
              summary
                ? `${t("advertising.stats.conversionRate")} ${
                    summary.attributions_count > 0 ? formatPercent(summary.conversion_rate, i18n.language) : none
                  }`
                : undefined
            }
          />
          <KpiTile
            panel
            icon={Banknote}
            label={t("advertising.stats.cost")}
            value={summary ? money(summary.cost) : none}
            hint={summary ? `${t("advertising.stats.cpa")} ${summary.cpa != null ? money(summary.cpa) : none}` : undefined}
          />
          <KpiTile
            panel
            icon={Wallet}
            label={t("advertising.stats.revenue")}
            value={summary ? money(summary.revenue) : none}
            trend={revenueTrend}
            hint={
              summary ? (
                <>
                  {t("advertising.stats.roi")}{" "}
                  <span className={`font-semibold ${roiClassName(summary.roi)}`}>
                    {summary.roi != null ? formatPercent(summary.roi, i18n.language, true) : none}
                  </span>
                </>
              ) : undefined
            }
          />
        </div>
      )}

      <div className="glass-panel relative shrink-0 rounded-3xl p-4">
        {state.kind === "ready" && isFetching && <RefetchSpinner />}
        <AnimatedHeight>

        {state.kind === "loading" && <Spinner size="page" />}
        {state.kind === "error" && (
          <ErrorState text={t("common.loadError")} size="page" />
        )}
        {state.kind === "ready" && state.items.length === 0 && (
          <EmptyState text={t(statusFilter ? "advertising.noMatches" : "advertising.empty")} size="page" />
        )}
        {state.kind === "ready" && state.items.length > 0 && (
          <>
            <div className={LIST_SCROLL_X_CLASS}>
              <div className={canViewSummary ? "min-w-[900px]" : "min-w-[560px]"}>
                <div className={`${gridClassName} ${GLASS_LIST_HEAD_CLASS}`}>
                  <span className="col-span-2">{t("advertising.columns.link")}</span>
                  {canViewSummary && (
                    <>
                      <span className="text-right">{t("advertising.stats.attributions")}</span>
                      <span className="text-right">{t("advertising.columns.paid")}</span>
                      <span className="text-right">{t("advertising.stats.conversionRate")}</span>
                    </>
                  )}
                  <span className="text-right">{t("advertising.stats.cost")}</span>
                  {canViewSummary && <span className="text-right">{t("advertising.stats.roi")}</span>}
                  <span>{t("advertising.columns.status")}</span>
                  <span />
                </div>

                <div className={LIST_BODY_CLASS}>
                  {state.items.map((link) => {
                    const metrics = metricsById.get(link.id);
                    const conversion =
                      metrics && metrics.attributions_count > 0 ? metrics.paid_count / metrics.attributions_count : null;

                    return (
                      <ListRow
                        key={link.id}
                        type="button"
                        onClick={() => setDetailsId(link.id)}
                        className={gridClassName}
                      >
                        <IconCircle icon={Link2} tone={link.is_active ? "success" : "neutral"} />
                        <CellText title={link.name} sub={link.code} mono />
                        {canViewSummary && (
                          <>
                            <span className="text-right text-[13px] font-semibold tabular-nums text-foreground">
                              {metrics?.attributions_count ?? none}
                            </span>
                            <span className="text-right text-[13px] tabular-nums text-foreground">
                              {metrics?.paid_count ?? none}
                            </span>
                            <span className="flex flex-col items-end gap-1">
                              <span className="text-[13px] tabular-nums text-foreground">
                                {conversion !== null ? formatPercent(String(conversion), i18n.language) : none}
                              </span>
                              <span className="h-[3px] w-14 overflow-hidden rounded-full glass-track">
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
                        {canViewSummary && (
                          <span
                            className={`text-right text-[13px] font-semibold tabular-nums ${roiClassName(metrics?.roi ?? null)}`}
                          >
                            {metrics?.roi != null ? formatPercent(metrics.roi, i18n.language, true) : none}
                          </span>
                        )}
                        <span>
                          <Badge tone={link.is_active ? "success" : "neutral"}>
                            {link.is_active ? t("advertising.status.active") : t("advertising.status.paused")}
                          </Badge>
                        </span>
                        <ChevronRight className="size-4 text-muted-foreground" />
                      </ListRow>

                    );
                  })}
                </div>

              </div>
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
          </>
        )}
        </AnimatedHeight>
      </div>
      </div>
      </LoadGate>
      </div>

      {isCreateOpen && (
        <AdLinkCreateDialog
          canGenerateCode={canGenerateCode}
          onClose={() => setIsCreateOpen(false)}
          onSaved={handleSaved}
        />
      )}

      {detailsLink && (
        <AdLinkDetailsDialog
          adLink={detailsLink}
          periodDays={period}
          createdFrom={createdFrom}
          canViewStats={canViewStats}
          canViewUsers={canViewUsers}
          canShare={canShare}
          canUpdate={canUpdate}
          canDelete={canDelete}
          onSaved={handleSaved}
          onDeleted={handleDeleted}
          onClose={() => {
            setDetailsId(null);
            dropUnmatched();
          }}
        />
      )}

    </div>
  );
}
