import { CalendarPlus, ChevronRight, Filter, Gift, Percent, Plus, Ticket, TicketCheck } from "lucide-react";
import { useMemo, useState, type ComponentType } from "react";
import { useTranslation } from "react-i18next";

import { listAddons } from "@entities/addons/api";
import { listPlans } from "@entities/plans/api";
import { daysUntil, expiryToneClassName } from "@entities/subscriptions/api";
import {
  DEFAULT_PAGE_SIZE,
  getPromocodeSummary,
  listPromocodes,
  type Promocode,
} from "@entities/promocodes/api";
import {
  describeReward,
  getPromocodeStatus,
  PROMOCODE_STATUS_BADGE_TONE,
  PROMOCODE_STATUSES,
  type PromocodeStatus,
  REWARD_TYPE_ICON,
  REWARD_TYPES,
} from "@entities/promocodes/display";
import { usePermissions } from "@entities/user/use-current-user";
import { PromocodeCreateDialog } from "@features/promocode-create/PromocodeCreateDialog";
import { PromocodeDetailsDialog } from "@features/promocode-details/PromocodeDetailsDialog";
import { useEntityChanged } from "@shared/lib/entity-dialogs";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { usePaginatedList } from "@shared/lib/use-paginated-list";
import { formatMoney } from "@shared/lib/format";
import { LoadGate, LoadGateHold } from "@shared/lib/load-gate";
import { AnimatedHeight } from "@shared/ui/glass/AnimatedHeight";
import { EmptyState, ErrorState } from "@shared/ui/glass/EmptyState";
import { IconCircle } from "@shared/ui/glass/IconCircle";
import { KpiTile } from "@shared/ui/KpiTile";
import { LoadMoreButton } from "@shared/ui/LoadMoreButton";
import { dotIcon } from "@shared/ui/option-icons";
import { SelectDropdown } from "@shared/ui/SelectDropdown";
import { RefetchSpinner, Spinner } from "@shared/ui/Spinner";
import { Button } from "@shared/ui/Button";
import { Badge } from "@shared/ui/Badge";
import { GLASS_LIST_HEAD_CLASS, LIST_BODY_CLASS, LIST_SCROLL_X_CLASS, PAGE_CLASS, PAGE_SCROLL_UNDER_BAR_CLASS, PAGE_TOOLBAR_CLASS } from "@shared/ui/classes";
import { formatDate } from "@shared/lib/relative-time";
import { ListRow } from "@shared/ui/ListRow";

const STATUS_DOTS: Record<PromocodeStatus, ComponentType<{ className?: string }>> = {
  ACTIVE: dotIcon("bg-success"),
  INACTIVE: dotIcon("bg-muted-foreground"),
  EXPIRED: dotIcon("bg-warning"),
  EXHAUSTED: dotIcon("bg-warning"),
};

const ROW_GRID_CLASSNAME = "grid grid-cols-[32px_minmax(0,1fr)_minmax(0,170px)_120px_110px_100px_16px] items-center gap-3";

export function PromocodesPage() {
  const { t, i18n } = useTranslation();
  const [addonsState] = useAsyncResource(listAddons);
  const [plansState] = useAsyncResource(listPlans);
  const addons = addonsState.kind === "ready" ? addonsState.data : [];
  const plans = plansState.kind === "ready" ? plansState.data : [];
  const [status, setStatus] = useState("");
  const [rewardType, setRewardType] = useState("");
  const filters = useMemo(() => ({ status, rewardType }), [status, rewardType]);
  const { state, setState, isFetching, isLoadingMore, hasMore, loadMore: handleLoadMore, reload } = usePaginatedList(
    (current, page, signal) => listPromocodes({ ...current, page, pageSize: DEFAULT_PAGE_SIZE }, signal),
    filters,
  );
  useEntityChanged("promocode", () => {
    reload();
    reloadSummary();
  });
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [detailsPromocode, setDetailsPromocode] = useState<Promocode | null>(null);

  const permissions = usePermissions();
  const canCreate = permissions.includes("PROMOCODES_CREATE");
  const canGenerateCode = permissions.includes("PROMOCODES_GENERATE_CODE");
  const canViewSummary = permissions.includes("PROMOCODES_SUMMARY_VIEW");

  const [summaryState, reloadSummary] = useAsyncResource((signal) =>
    canViewSummary ? getPromocodeSummary(signal) : Promise.resolve(null),
  );
  const summary = summaryState.kind === "ready" ? summaryState.data : null;

  const visibleItems = state.kind === "ready" ? state.items : [];
  const hasFilters = Boolean(status || rewardType);

  const handleSaved = (promo: Promocode) => {
    reloadSummary();
    setState((prev) => {
      if (prev.kind !== "ready") return prev;
      const exists = prev.items.some((item) => item.id === promo.id);
      return exists
        ? { ...prev, items: prev.items.map((item) => (item.id === promo.id ? promo : item)) }
        : { kind: "ready", items: [promo, ...prev.items], total: prev.total + 1 };
    });
  };

  const handleDeleted = (promo: Promocode) => {
    reloadSummary();
    setState((prev) =>
      prev.kind === "ready"
        ? { kind: "ready", items: prev.items.filter((item) => item.id !== promo.id), total: prev.total - 1 }
        : prev,
    );
  };

  const none = t("common.none");
  const relativeTime = new Intl.RelativeTimeFormat(i18n.language, { numeric: "auto" });

  return (
    // as the transactions page: the filter bar floats over a scroller of its own, whose fade clears the bar
    <div data-fills-main className={PAGE_CLASS}>
      <div className={PAGE_TOOLBAR_CLASS}>
        <div className="min-w-40 flex-1 md:min-w-0">
          <SelectDropdown
            id="promocodes-status"
            value={status}
            onChange={setStatus}
            icon={Filter}
            size="compact"
            glassPopover
            placeholder={t("promocodes.filters.statusAll")}
            options={[
              { value: "", label: t("promocodes.filters.statusAll"), icon: Filter },
              ...PROMOCODE_STATUSES.map((value) => ({ value, label: t(`promocodes.status.${value}`), icon: STATUS_DOTS[value] })),
            ]}
          />
        </div>
        <div className="min-w-40 flex-1 md:min-w-0">
          <SelectDropdown
            id="promocodes-reward-type"
            value={rewardType}
            onChange={setRewardType}
            icon={Gift}
            size="compact"
            glassPopover
            placeholder={t("promocodes.filters.rewardAll")}
            options={[
              { value: "", label: t("promocodes.filters.rewardAll"), icon: Gift },
              ...REWARD_TYPES.map((value) => ({
                value,
                label: t(`promocodes.rewardType.${value}`),
                icon: REWARD_TYPE_ICON[value],
              })),
            ]}
          />
        </div>
        {canCreate && (
          <Button variant="glassAccent" type="button" onClick={() => setIsCreateOpen(true)} className="ml-auto">
            <Plus className="size-4" />
            {t("promocodes.create.button")}
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
            icon={Ticket}
            label={t("promocodes.stats.total")}
            value={summary ? String(summary.total_count) : none}
            hint={summary ? t("promocodes.stats.active", { count: summary.active_count }) : undefined}
          />
          <KpiTile
            panel
            icon={TicketCheck}
            label={t("promocodes.stats.activations")}
            value={summary ? String(summary.activations_count) : none}
            hint={summary ? t("promocodes.stats.users", { count: summary.activated_users_count }) : undefined}
          />
          <KpiTile
            panel
            icon={CalendarPlus}
            label={t("promocodes.stats.grantedDays")}
            value={summary ? summary.granted_days.toLocaleString(i18n.language) : none}
            hint={
              summary ? t("promocodes.stats.subscriptions", { count: summary.granted_subscriptions_count }) : undefined
            }
          />
          <KpiTile
            panel
            icon={Percent}
            label={t("promocodes.stats.discounts")}
            value={summary ? formatMoney(summary.discount_amount, summary.report_currency, i18n.language) : none}
            hint={summary ? t("promocodes.stats.discountedOrders", { count: summary.discounted_orders_count }) : undefined}
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
        {state.kind === "ready" && visibleItems.length === 0 && (
          <EmptyState text={t(hasFilters ? "promocodes.noMatches" : "promocodes.empty")} size="page" />
        )}
        {state.kind === "ready" && visibleItems.length > 0 && (
          <>
            <div className={LIST_SCROLL_X_CLASS}>
              <div className="min-w-[800px]">
                <div className={`${ROW_GRID_CLASSNAME} ${GLASS_LIST_HEAD_CLASS}`}>
                  <span className="col-span-2">{t("promocodes.columns.code")}</span>
                  <span>{t("promocodes.columns.availability")}</span>
                  <span>{t("promocodes.columns.used")}</span>
                  <span>{t("promocodes.details.expires")}</span>
                  <span>{t("promocodes.columns.status")}</span>
                  <span />
                </div>
                <div className={LIST_BODY_CLASS}>
                  {visibleItems.map((promo) => {
                    const promoStatus = getPromocodeStatus(promo);
                    return (
                      <ListRow
                        key={promo.id}
                        type="button"
                        onClick={() => setDetailsPromocode(promo)}
                        className={ROW_GRID_CLASSNAME}
                      >
                        <IconCircle icon={Ticket} tone={promoStatus === "ACTIVE" ? "success" : "neutral"} />
                        <span className="min-w-0">
                          <span className="block truncate font-mono text-[13px] font-medium text-foreground">{promo.code}</span>
                          <span className="block truncate text-[12px] text-muted-foreground">
                            {t(`promocodes.rewardType.${promo.reward_type}`)}
                            {" · "}
                            <span className="font-medium text-foreground/80">{describeReward(promo, addons, plans, t)}</span>
                          </span>
                        </span>
                        <span className="truncate text-[13px] text-foreground">
                          {t(`promocodes.availability.${promo.availability}`)}
                        </span>
                        <span className="text-[13px] tabular-nums text-foreground">
                          {promo.activations_count}{" "}
                          <span className="text-muted-foreground">
                            {t("promocodes.details.ofMax", { max: promo.max_activations ?? "∞" })}
                          </span>
                        </span>
                        <span className="tabular-nums">
                          {promo.expires_at ? (
                            <>
                              <span className="block text-[13px] text-foreground">
                                {formatDate(promo.expires_at, i18n.language)}
                              </span>
                              <span className={`block text-[12px] ${expiryToneClassName(daysUntil(promo.expires_at))}`}>
                                {relativeTime.format(daysUntil(promo.expires_at), "day")}
                              </span>
                            </>
                          ) : (
                            <span className="text-[13px] text-foreground">{t("promocodes.noExpiry")}</span>
                          )}
                        </span>
                        <span>
                          <Badge tone={PROMOCODE_STATUS_BADGE_TONE[promoStatus]}>{t(`promocodes.status.${promoStatus}`)}</Badge>
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
        <PromocodeCreateDialog
          canGenerateCode={canGenerateCode}
          addons={addons}
          plans={plans}
          onClose={() => setIsCreateOpen(false)}
          onSaved={handleSaved}
        />
      )}

      {detailsPromocode && (
        <PromocodeDetailsDialog
          promocode={detailsPromocode}
          addons={addons}
          plans={plans}
          onSaved={handleSaved}
          onDeleted={handleDeleted}
          onClose={() => setDetailsPromocode(null)}
        />
      )}

    </div>
  );
}
