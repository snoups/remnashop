import { ChevronRight, Filter, Gift, Plus, Ticket } from "lucide-react";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";

import { listAddons } from "@entities/addons/api";
import { listPlans } from "@entities/plans/api";
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
  REWARD_TYPES,
} from "@entities/promocodes/display";
import { usePermissions } from "@entities/user/use-current-user";
import { PromocodeCreateDialog } from "@features/promocode-create/PromocodeCreateDialog";
import { PromocodeDetailsDialog } from "@features/promocode-details/PromocodeDetailsDialog";
import { useEntityChanged } from "@shared/lib/entity-dialogs";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { usePaginatedList } from "@shared/lib/use-paginated-list";
import { formatMoney } from "@shared/lib/format";
import { EmptyState, ErrorState } from "@shared/ui/EmptyState";
import { KpiTile } from "@shared/ui/KpiTile";
import { LoadMoreButton } from "@shared/ui/LoadMoreButton";
import { SelectDropdown } from "@shared/ui/SelectDropdown";
import { Spinner } from "@shared/ui/Spinner";
import { Button } from "@shared/ui/Button";
import { Badge } from "@shared/ui/Badge";
import { Card } from "@shared/ui/Card";
import { EYEBROW_CLASS, LIST_BODY_CLASS, LIST_HEAD_CLASS } from "@shared/ui/classes";
import { formatDate } from "@shared/lib/relative-time";
import { ListRow } from "@shared/ui/ListRow";

const ROW_GRID_CLASSNAME = "grid grid-cols-[36px_minmax(0,1fr)_120px_110px_100px_16px] items-center gap-3";

export function PromocodesPage() {
  const { t, i18n } = useTranslation();
  const [addonsState] = useAsyncResource(listAddons);
  const [plansState] = useAsyncResource(listPlans);
  const addons = addonsState.kind === "ready" ? addonsState.data : [];
  const plans = plansState.kind === "ready" ? plansState.data : [];
  const [status, setStatus] = useState("");
  const [rewardType, setRewardType] = useState("");
  // set by the header search's deep link; no local search box
  const [searchParams] = useSearchParams();
  const search = (searchParams.get("search") ?? "").trim();
  const filters = useMemo(() => ({ status, rewardType, search }), [status, rewardType, search]);
  const { state, setState, isLoadingMore, hasMore, loadMore: handleLoadMore, reload } = usePaginatedList(
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
  const hasFilters = Boolean(status || rewardType || search);

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
  const usedCount = (promo: Promocode): number | undefined =>
    summary ? (summary.activations_by_promocode[promo.id] ?? 0) : undefined;

  return (
    <div className="flex flex-col gap-4">
      {canViewSummary && (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <KpiTile
            label={t("promocodes.stats.promocodes")}
            value={summary ? String(summary.total_count) : none}
            hint={summary ? t("promocodes.stats.active", { count: summary.active_count }) : undefined}
          />
          <KpiTile
            label={t("promocodes.stats.activations")}
            value={summary ? String(summary.activations_count) : none}
            hint={summary ? t("promocodes.stats.users", { count: summary.activated_users_count }) : undefined}
          />
          <KpiTile
            label={t("promocodes.stats.grantedDays")}
            value={summary ? summary.granted_days.toLocaleString(i18n.language) : none}
            hint={
              summary ? t("promocodes.stats.subscriptions", { count: summary.granted_subscriptions_count }) : undefined
            }
          />
          <KpiTile
            label={t("promocodes.stats.discounts")}
            value={summary ? formatMoney(summary.discount_amount, summary.report_currency, i18n.language) : none}
            hint={summary ? t("promocodes.stats.discountedOrders", { count: summary.discounted_orders_count }) : undefined}
          />
        </div>
      )}

      <Card>
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex min-w-40 flex-1 flex-col gap-1.5">
            <label className={EYEBROW_CLASS}>{t("promocodes.filters.status")}</label>
            <SelectDropdown
              id="promocodes-status"
              value={status}
              onChange={setStatus}
              icon={Filter}
              placeholder={t("promocodes.filters.statusAll")}
              options={[
                { value: "", label: t("promocodes.filters.statusAll") },
                ...PROMOCODE_STATUSES.map((value) => ({ value, label: t(`promocodes.status.${value}`) })),
              ]}
            />
          </div>
          <div className="flex min-w-40 flex-1 flex-col gap-1.5">
            <label className={EYEBROW_CLASS}>{t("promocodes.filters.reward")}</label>
            <SelectDropdown
              id="promocodes-reward-type"
              value={rewardType}
              onChange={setRewardType}
              icon={Gift}
              placeholder={t("promocodes.filters.rewardAll")}
              options={[
                { value: "", label: t("promocodes.filters.rewardAll") },
                ...REWARD_TYPES.map((value) => ({ value, label: t(`promocodes.rewardType.${value}`) })),
              ]}
            />
          </div>
          {canCreate && (
            <Button variant="solid" size="field" type="button" className="ml-auto" onClick={() => setIsCreateOpen(true)}>
              <Plus className="size-3.5" />
              {t("promocodes.create.button")}
            </Button>
          )}
        </div>
      </Card>

      <Card>
        {state.kind === "loading" && <Spinner size="page" />}
        {state.kind === "error" && (
          <ErrorState text={t("common.loadError")} size="page" />
        )}
        {state.kind === "ready" && visibleItems.length === 0 && (
          <EmptyState text={t(hasFilters ? "promocodes.noMatches" : "promocodes.empty")} size="page" />
        )}
        {state.kind === "ready" && visibleItems.length > 0 && (
          <>
            <div className={`${ROW_GRID_CLASSNAME} ${LIST_HEAD_CLASS}`}>
              <span className="col-span-2">{t("promocodes.columns.code")}</span>
              <span>{t("promocodes.columns.used")}</span>
              <span>{t("promocodes.details.expires")}</span>
              <span>{t("promocodes.columns.status")}</span>
              <span />
            </div>
            <div className={LIST_BODY_CLASS}>
              {visibleItems.map((promo) => {
                const promoStatus = getPromocodeStatus(promo);
                const used = usedCount(promo);
                return (
                  <ListRow
                    key={promo.id}
                    type="button"
                    onClick={() => setDetailsPromocode(promo)}
                    className={ROW_GRID_CLASSNAME}
                  >
                    <span
                      className={`flex size-9 items-center justify-center rounded-full ${
                        promoStatus === "ACTIVE" ? "bg-success/10 text-success" : "bg-white/[0.06] text-muted-foreground"
                      }`}
                    >
                      <Ticket className="size-4" />
                    </span>
                    <span className="min-w-0">
                      <span className="flex min-w-0 items-center gap-1.5">
                        <span className="truncate font-mono text-[13px] font-bold text-foreground">{promo.code}</span>
                        {promo.is_reusable && <Badge tone="accent">&infin;</Badge>}
                      </span>
                      <span className="block truncate text-[12px] text-muted-foreground">
                        <span className="font-medium text-foreground/80">{describeReward(promo, addons, plans, t)}</span>
                        {" · "}
                        {t(`promocodes.availability.${promo.availability}`)}
                      </span>
                    </span>
                    <span className="text-[13px] tabular-nums text-foreground">
                      {used ?? none}
                      <span className="text-muted-foreground">
                        {" / "}
                        {promo.max_activations ?? "∞"}
                      </span>
                    </span>
                    <span className="text-[13px] tabular-nums text-foreground">
                      {promo.expires_at
                        ? formatDate(promo.expires_at, i18n.language)
                        : t("promocodes.noExpiry")}
                    </span>
                    <span>
                      <Badge tone={PROMOCODE_STATUS_BADGE_TONE[promoStatus]}>{t(`promocodes.status.${promoStatus}`)}</Badge>
                    </span>
                    <ChevronRight className="size-4 text-muted-foreground" />
                  </ListRow>
                );
              })}
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
      </Card>

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
          usedCount={usedCount(detailsPromocode)}
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
