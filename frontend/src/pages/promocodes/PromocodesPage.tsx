import { AlertCircle, ChevronRight, Filter, Gift, Plus, Ticket } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";

import { type AddOnListItem, listAddons } from "@entities/addons/api";
import { type Plan, listPlans } from "@entities/plans/api";
import {
  DEFAULT_PAGE_SIZE,
  deletePromocode,
  getPromocodeSummary,
  listPromocodes,
  type Promocode,
  type PromocodeSummary,
} from "@entities/promocodes/api";
import {
  describeReward,
  getPromocodeStatus,
  PROMOCODE_STATUS_BADGE_TONE,
  PROMOCODE_STATUSES,
  REWARD_TYPES,
} from "@entities/promocodes/display";
import { useCurrentUser } from "@entities/user/use-current-user";
import { PromocodeCreateDialog } from "@features/promocode-create/PromocodeCreateDialog";
import { PromocodeDetailsDialog } from "@features/promocode-details/PromocodeDetailsDialog";
import { getErrorMessage } from "@shared/api/http";
import { formatMoney } from "@shared/lib/format";
import { bounceTap } from "@shared/lib/bounceState";
import { toast } from "@shared/lib/toast";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { EmptyState } from "@shared/ui/EmptyState";
import { KpiTile } from "@shared/ui/KpiTile";
import { LoadMoreButton } from "@shared/ui/LoadMoreButton";
import { SelectDropdown } from "@shared/ui/SelectDropdown";
import { Spinner } from "@shared/ui/Spinner";
import { Button } from "@shared/ui/Button";
import { Badge } from "@shared/ui/Badge";
import { Card } from "@shared/ui/Card";
import { EYEBROW_CLASS, LIST_BODY_CLASS, LIST_HEAD_CLASS, LIST_ROW_CLASS } from "@shared/ui/classes";
import { formatDate } from "@shared/lib/relative-time";

type LoadState = { kind: "loading" } | { kind: "error" } | { kind: "ready"; items: Promocode[]; total: number };

const ROW_GRID_CLASSNAME = "grid grid-cols-[36px_minmax(0,1fr)_120px_110px_100px_16px] items-center gap-3";

export function PromocodesPage() {
  const { t, i18n } = useTranslation();
  const [state, setState] = useState<LoadState>({ kind: "loading" });
  const [addons, setAddons] = useState<AddOnListItem[]>([]);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [status, setStatus] = useState("");
  const [rewardType, setRewardType] = useState("");
  // set by the header search's deep link; no local search box
  const [searchParams] = useSearchParams();
  const search = (searchParams.get("search") ?? "").trim();
  const [page, setPage] = useState(1);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  // a load-more started before a filter change must not append to the new list
  const loadGenRef = useRef(0);
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [summary, setSummary] = useState<PromocodeSummary | null>(null);
  // bumped after create/edit/delete so the metrics catch up with the list
  const [summaryVersion, setSummaryVersion] = useState(0);
  // an id, not the row: the dialog then follows edits/toggles made from inside it
  const [detailsId, setDetailsId] = useState<number | null>(null);
  const [pendingDelete, setPendingDelete] = useState<Promocode | null>(null);

  const currentUserState = useCurrentUser();
  const permissions =
    currentUserState.kind === "ready" ? currentUserState.data.effective_permissions : [];
  const canCreate = permissions.includes("PROMOCODES_CREATE");
  const canUpdate = permissions.includes("PROMOCODES_UPDATE");
  const canDelete = permissions.includes("PROMOCODES_DELETE");
  const canGenerateCode = permissions.includes("PROMOCODES_GENERATE_CODE");
  const canViewSummary = permissions.includes("PROMOCODES_SUMMARY_VIEW");
  const canViewUsers = permissions.includes("PROMOCODES_USERS_VIEW");

  useEffect(() => {
    const controller = new AbortController();
    listAddons(controller.signal)
      .then((items) => {
        if (!controller.signal.aborted) setAddons(items);
      })
      .catch(() => {
        if (!controller.signal.aborted) setAddons([]);
      });
    listPlans(controller.signal)
      .then((items) => {
        if (!controller.signal.aborted) setPlans(items);
      })
      .catch(() => {
        if (!controller.signal.aborted) setPlans([]);
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!canViewSummary) return;
    const controller = new AbortController();
    getPromocodeSummary(controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) setSummary(result);
      })
      .catch(() => {
        // metrics are secondary; the list stays usable with dashes in their place
      });
    return () => controller.abort();
  }, [canViewSummary, summaryVersion]);

  useEffect(() => {
    const controller = new AbortController();
    loadGenRef.current += 1;
    setPage(1);
    listPromocodes({ status, rewardType, search, page: 1, pageSize: DEFAULT_PAGE_SIZE }, controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) setState({ kind: "ready", items: result.items, total: result.total });
      })
      .catch(() => {
        if (!controller.signal.aborted) setState((prev) => (prev.kind === "ready" ? prev : { kind: "error" }));
      });
    return () => controller.abort();
  }, [status, rewardType, search]);

  // offset drift on a page boundary after create/delete, switch to keyset if it bites.
  const handleLoadMore = async () => {
    const gen = loadGenRef.current;
    const nextPage = page + 1;
    setIsLoadingMore(true);
    try {
      const result = await listPromocodes({ status, rewardType, search, page: nextPage, pageSize: DEFAULT_PAGE_SIZE });
      if (gen !== loadGenRef.current) return;
      setState((prev) =>
        prev.kind === "ready" ? { kind: "ready", items: [...prev.items, ...result.items], total: result.total } : prev,
      );
      setPage(nextPage);
    } catch {
      // keep current items; the button stays available to retry
    } finally {
      setIsLoadingMore(false);
    }
  };

  const visibleItems = state.kind === "ready" ? state.items : [];
  const hasFilters = Boolean(status || rewardType || search);

  const handleSaved = (promo: Promocode) => {
    setSummaryVersion((version) => version + 1);
    setState((prev) => {
      if (prev.kind !== "ready") return prev;
      const exists = prev.items.some((item) => item.id === promo.id);
      return exists
        ? { ...prev, items: prev.items.map((item) => (item.id === promo.id ? promo : item)) }
        : { kind: "ready", items: [promo, ...prev.items], total: prev.total + 1 };
    });
  };

  const handleDelete = async (promo: Promocode) => {
    try {
      await deletePromocode(promo.id);
      setSummaryVersion((version) => version + 1);
      setState((prev) =>
        prev.kind === "ready"
          ? { kind: "ready", items: prev.items.filter((item) => item.id !== promo.id), total: prev.total - 1 }
          : prev,
      );
    } catch (err) {
      toast.error(getErrorMessage(err, t("promocodes.delete.error")));
    }
  };

  const none = t("promocodes.stats.none");
  const usedCount = (promo: Promocode): number | undefined =>
    summary ? (summary.activations_by_promocode[promo.id] ?? 0) : undefined;
  const detailsPromocode = state.kind === "ready" ? state.items.find((item) => item.id === detailsId) : undefined;

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
          <div className="flex flex-col items-center gap-2 py-12 text-error">
            <AlertCircle className="size-5" />
            <p className="text-sm">{t("promocodes.loadError")}</p>
          </div>
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
                  <motion.button
                    key={promo.id}
                    type="button"
                    onClick={() => setDetailsId(promo.id)}
                    {...bounceTap(0.03)}
                    className={`${ROW_GRID_CLASSNAME} w-full ${LIST_ROW_CLASS} text-left hover:bg-white/[0.04]`}
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
                        <span className="truncate font-mono text-[13.5px] font-bold text-foreground">{promo.code}</span>
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
                  </motion.button>
                );
              })}
            </div>

            {state.kind === "ready" && state.items.length < state.total && (
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
          canViewUsers={canViewUsers}
          canUpdate={canUpdate}
          canDelete={canDelete}
          onSaved={handleSaved}
          onClose={(followUp) => {
            if (followUp === "delete") setPendingDelete(detailsPromocode);
            setDetailsId(null);
          }}
        />
      )}

      {pendingDelete && (
        <ConfirmDialog
          title={t("promocodes.delete.title")}
          message={t("promocodes.delete.confirm", { code: pendingDelete.code })}
          confirmLabel={t("promocodes.delete.confirmButton")}
          cancelLabel={t("promocodes.delete.cancelButton")}
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
