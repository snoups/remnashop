import {
  closestCenter,
  DndContext,
  type DragEndEvent,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import { arrayMove, rectSortingStrategy, SortableContext, sortableKeyboardCoordinates, useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import {
  AlertCircle,
  ArrowDownUp,
  GripVertical,
  Layers,
  Pencil,
  Plus,
  ShieldCheck,
  Smartphone,
  Trash2,
} from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { formatMoney } from "@entities/advertising/format";
import { deletePlan, listPlans, type Plan, type PlanAvailability, reorderPlans, updatePlan } from "@entities/plans/api";
import { getPriceBook } from "@entities/pricing/api";
import { useCurrentUser } from "@entities/user/use-current-user";
import { PlanAccessDialog } from "@features/plan-access/PlanAccessDialog";
import { PlanEditDialog } from "@features/plan-edit/PlanEditDialog";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { ActionMenu, type ActionMenuItem } from "@shared/ui/ActionMenu";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { EmptyState } from "@shared/ui/EmptyState";
import { SegmentedPills } from "@shared/ui/SegmentedPills";
import { Spinner } from "@shared/ui/Spinner";
import { Switch } from "@shared/ui/Switch";
import { Button } from "@shared/ui/Button";
import { Badge } from "@shared/ui/Badge";
import { Tag } from "@shared/ui/Tag";
import { IconButton } from "@shared/ui/IconButton";

type LoadState = { kind: "loading" } | { kind: "error" } | { kind: "ready"; items: Plan[] };
type Filter = "all" | "active" | "inactive";

const RESTRICTED_AVAILABILITIES: ReadonlySet<PlanAvailability> = new Set(["INVITED", "ALLOWED", "LINK"]);
const CARD_HEIGHT_CLASSNAME = "min-h-[318px]";

export function PlansPage() {
  const { t } = useTranslation();
  const [state, setState] = useState<LoadState>({ kind: "loading" });
  const [anchorCurrency, setAnchorCurrency] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [editingPlan, setEditingPlan] = useState<Plan | null | "new">(null);
  const [accessPlan, setAccessPlan] = useState<Plan | null>(null);
  const [pendingDelete, setPendingDelete] = useState<Plan | null>(null);
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const currentUserState = useCurrentUser();
  const permissions =
    currentUserState.kind === "ready" ? currentUserState.data.effective_permissions : [];
  const canCreate = permissions.includes("PLANS_CREATE");
  const canUpdate = permissions.includes("PLANS_UPDATE");
  const canDelete = permissions.includes("PLANS_DELETE");
  const canManageAccess = permissions.includes("PLANS_ACCESS_MANAGE");
  const canReorder = permissions.includes("PLANS_ORDER_MANAGE");
  const canViewPricing = permissions.includes("PRICING_VIEW");

  useEffect(() => {
    const controller = new AbortController();
    setState({ kind: "loading" });
    listPlans(controller.signal)
      .then((items) => {
        if (!controller.signal.aborted) setState({ kind: "ready", items });
      })
      .catch(() => {
        if (!controller.signal.aborted) setState({ kind: "error" });
      });
    return () => controller.abort();
  }, []);

  // base_price is in the anchor currency, which only the price book knows
  useEffect(() => {
    if (!canViewPricing) return;
    const controller = new AbortController();
    getPriceBook(controller.signal)
      .then((book) => {
        if (!controller.signal.aborted) setAnchorCurrency(book.settings.anchor_currency);
      })
      .catch(() => {});
    return () => controller.abort();
  }, [canViewPricing]);

  const handleSaved = (plan: Plan) => {
    if (state.kind !== "ready") return;
    const exists = state.items.some((item) => item.id === plan.id);
    setState({
      kind: "ready",
      items: exists ? state.items.map((item) => (item.id === plan.id ? plan : item)) : [...state.items, plan],
    });
  };

  const handleToggleActive = async (plan: Plan) => {
    if (state.kind !== "ready") return;
    const previous = state.items;
    setState({
      kind: "ready",
      items: state.items.map((item) => (item.id === plan.id ? { ...item, is_active: !item.is_active } : item)),
    });
    try {
      await updatePlan(plan.id, { is_active: !plan.is_active });
    } catch (err) {
      setState({ kind: "ready", items: previous });
      toast.error(getErrorMessage(err, t("plans.edit.error")));
    }
  };

  const handleDragEnd = async ({ active, over }: DragEndEvent) => {
    if (state.kind !== "ready" || !over || active.id === over.id) return;
    const from = state.items.findIndex((plan) => plan.id === active.id);
    const to = state.items.findIndex((plan) => plan.id === over.id);
    const previous = state.items;
    const reordered = arrayMove(state.items, from, to);
    setState({ kind: "ready", items: reordered });
    try {
      const result = await reorderPlans(reordered.map((plan) => plan.id));
      setState({ kind: "ready", items: result });
    } catch (err) {
      setState({ kind: "ready", items: previous });
      toast.error(getErrorMessage(err, t("plans.reorderError")));
    }
  };

  const handleDelete = async (plan: Plan) => {
    try {
      await deletePlan(plan.id);
      if (state.kind === "ready") {
        setState({ kind: "ready", items: state.items.filter((item) => item.id !== plan.id) });
      }
    } catch (err) {
      toast.error(getErrorMessage(err, t("plans.delete.error")));
    }
  };

  const visibleItems =
    state.kind === "ready"
      ? state.items.filter((plan) => filter === "all" || plan.is_active === (filter === "active"))
      : [];
  // reordering a filtered subset has no well-defined position in the full list
  const isSortable = canReorder && filter === "all";

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2.5">
          <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] text-foreground backdrop-blur-md">
            <Layers className="size-4" />
          </div>
          <div className="min-w-0">
            <h2 className="flex items-center gap-2 text-sm font-bold text-foreground">
              {t("plans.title")}
              {state.kind === "ready" && (
                <span className="text-[11.5px] font-normal tabular-nums text-muted-foreground">
                  {state.items.length} &middot;{" "}
                  {t("plans.activeCount", { count: state.items.filter((plan) => plan.is_active).length })}
                </span>
              )}
            </h2>
            <p className="mt-0.5 text-[12.5px] text-muted-foreground">{t("plans.description")}</p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <SegmentedPills
            value={filter}
            onChange={setFilter}
            ariaLabel={t("plans.filters.label")}
            options={[
              { value: "all", label: t("plans.filters.all") },
              { value: "active", label: t("plans.filters.active") },
              { value: "inactive", label: t("plans.filters.inactive") },
            ]}
          />
          {canCreate && (
            <Button
              variant="solid"
              type="button"
              onClick={() => setEditingPlan("new")}
            >
              <Plus className="size-3.5" />
              {t("plans.create.button")}
            </Button>
          )}
        </div>
      </div>

      {state.kind === "loading" && <Spinner size="page" />}
      {state.kind === "error" && (
        <div className="flex flex-col items-center gap-2 py-12 text-error">
          <AlertCircle className="size-5" />
          <p className="text-sm">{t("plans.loadError")}</p>
        </div>
      )}
      {state.kind === "ready" && visibleItems.length === 0 && !canCreate && (
        <EmptyState text={t(state.items.length === 0 ? "plans.empty" : "plans.noMatches")} size="page" />
      )}
      {state.kind === "ready" && (visibleItems.length > 0 || canCreate) && (
        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={(e) => void handleDragEnd(e)}>
          <SortableContext items={visibleItems.map((plan) => plan.id)} strategy={rectSortingStrategy}>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {visibleItems.map((plan) => {
                const menuItems: ActionMenuItem[] = [];
                if (canUpdate) {
                  menuItems.push({ label: t("plans.edit.button"), icon: Pencil, onClick: () => setEditingPlan(plan) });
                }
                if (canManageAccess) {
                  menuItems.push({
                    label: t("plans.access.button"),
                    icon: ShieldCheck,
                    onClick: () => setAccessPlan(plan),
                  });
                }
                if (canDelete) {
                  menuItems.push({
                    label: t("plans.delete.button"),
                    icon: Trash2,
                    variant: "danger",
                    onClick: () => setPendingDelete(plan),
                  });
                }
                return (
                  <PlanCard
                    key={plan.id}
                    plan={plan}
                    anchorCurrency={anchorCurrency}
                    sortable={isSortable}
                    menuItems={menuItems}
                    onToggleActive={canUpdate ? () => void handleToggleActive(plan) : undefined}
                  />
                );
              })}
              {canCreate && (
                <button
                  type="button"
                  onClick={() => setEditingPlan("new")}
                  className={`group flex flex-col items-center justify-center gap-2.5 rounded-[20px] border-[1.5px] border-dashed border-white/[0.16] text-[13px] font-medium text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground ${CARD_HEIGHT_CLASSNAME}`}
                >
                  <span className="flex size-11 items-center justify-center rounded-full bg-accent text-primary transition-colors group-hover:bg-primary/20">
                    <Plus className="size-[18px]" />
                  </span>
                  {t("plans.create.button")}
                </button>
              )}
            </div>
          </SortableContext>
        </DndContext>
      )}

      {editingPlan !== null && (
        <PlanEditDialog
          plan={editingPlan === "new" ? null : editingPlan}
          anchorCurrency={anchorCurrency}
          onClose={() => setEditingPlan(null)}
          onSaved={handleSaved}
        />
      )}

      {accessPlan && (
        <PlanAccessDialog plan={accessPlan} onClose={() => setAccessPlan(null)} onSaved={handleSaved} />
      )}

      {pendingDelete && (
        <ConfirmDialog
          title={t("plans.delete.confirmTitle")}
          message={t("plans.delete.confirm", { name: pendingDelete.name })}
          confirmLabel={t("plans.delete.confirmButton")}
          cancelLabel={t("plans.delete.cancelButton")}
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

function PlanCard({
  plan,
  anchorCurrency,
  sortable,
  menuItems,
  onToggleActive,
}: {
  plan: Plan;
  anchorCurrency: string | null;
  sortable: boolean;
  menuItems: ActionMenuItem[];
  onToggleActive?: () => void;
}) {
  const { t, i18n } = useTranslation();
  const { attributes, listeners, setNodeRef, setActivatorNodeRef, transform, transition, isDragging } = useSortable({
    id: plan.id,
    disabled: !sortable,
  });

  const durations = plan.durations.slice().sort((a, b) => a.order_index - b.order_index);
  const cheapest = durations.reduce<(typeof durations)[number] | null>(
    (min, d) => (min === null || Number(d.base_price) < Number(min.base_price) ? d : min),
    null,
  );
  const isRestricted = RESTRICTED_AVAILABILITIES.has(plan.availability);

  return (
    <article
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={`relative flex flex-col gap-3.5 rounded-[20px] border p-4 transition-[border-color,background-color,opacity] ${CARD_HEIGHT_CLASSNAME} ${
        plan.tag ? "border-primary/30 bg-primary/[0.05]" : "border-white/[0.08] bg-white/[0.03] hover:border-white/[0.16]"
      } ${plan.is_active ? "" : "opacity-55"} ${isDragging ? "z-10 shadow-2xl shadow-black/50" : ""}`}
    >
      <div className="flex items-start gap-2.5">
        <span
          aria-hidden
          className={`flex size-9 shrink-0 items-center justify-center rounded-full ${
            plan.is_active ? "bg-primary/10 text-primary" : "bg-white/[0.06] text-muted-foreground"
          }`}
        >
          <Layers className="size-4" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="truncate text-[15px] font-bold text-foreground">{plan.name}</span>
            {plan.is_trial && (
              <Badge tone="warning">
                {t("plans.edit.isTrialLabel")}
              </Badge>
            )}
            {plan.tag && (
              <Badge tone="accent">
                {plan.tag}
              </Badge>
            )}
          </div>
          <p className="truncate font-mono text-[11.5px] text-muted-foreground">
            {plan.public_code} &middot; {t(`plans.edit.type.${plan.type}`)}
          </p>
        </div>
        <div className="-mr-1.5 -mt-1.5 flex shrink-0 items-center">
          {sortable && (
            <IconButton size="8" className="cursor-grab touch-none active:cursor-grabbing"
              ref={setActivatorNodeRef}
              aria-label={t("plans.dragHandle", { name: plan.name })}
              {...attributes}
              {...listeners}
            >
              <GripVertical className="size-4" />
            </IconButton>
          )}
          {menuItems.length > 0 && <ActionMenu items={menuItems} />}
        </div>
      </div>

      {cheapest && (
        <div className="flex items-baseline gap-1.5">
          <span className="text-[12px] text-muted-foreground">{t("plans.priceFrom")}</span>
          <span className="text-[26px] font-bold tabular-nums tracking-tight text-foreground">
            {anchorCurrency
              ? formatMoney(cheapest.base_price, anchorCurrency, i18n.language)
              : new Intl.NumberFormat(i18n.language).format(Number(cheapest.base_price))}
          </span>
          <span className="text-[12px] text-muted-foreground">{t("plans.perDays", { count: cheapest.days })}</span>
        </div>
      )}

      <div className="flex flex-col gap-1.5 rounded-[14px] bg-white/[0.035] px-3 py-2.5 text-[12.5px] text-foreground">
        <span className="flex items-center gap-2">
          <ArrowDownUp className="size-3.5 shrink-0 text-muted-foreground" />
          <span className="flex-1">{plan.traffic_limit === 0 ? t("plans.unlimited") : `${plan.traffic_limit} GB`}</span>
          {plan.traffic_limit !== 0 && (
            <span className="text-muted-foreground">{t(`plans.edit.strategy.${plan.traffic_limit_strategy}`)}</span>
          )}
        </span>
        <span className="flex items-center gap-2">
          <Smartphone className="size-3.5 shrink-0 text-muted-foreground" />
          {plan.device_limit === 0 ? t("plans.unlimited") : t("plans.devices", { count: plan.device_limit })}
        </span>
      </div>

      {durations.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {durations.map((d) => (
            <Tag key={d.days}>
              {t("plans.daysShort", { count: d.days })}
            </Tag>
          ))}
        </div>
      )}

      <div className="mt-auto flex items-center justify-between gap-2 border-t border-white/[0.07] pt-3">
        <Badge tone={isRestricted ? "violet" : "neutral"} className="min-w-0">
          <span className="truncate">{t(`plans.access.availability.${plan.availability}`)}</span>
        </Badge>
        {onToggleActive && (
          <Switch checked={plan.is_active} onChange={onToggleActive} ariaLabel={t("plans.edit.isActiveLabel")} />
        )}
      </div>
    </article>
  );
}
