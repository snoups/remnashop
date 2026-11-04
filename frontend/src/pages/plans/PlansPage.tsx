import {
  closestCenter,
  DndContext,
  type DragEndEvent,
  KeyboardSensor,
  MouseSensor,
  TouchSensor,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import { arrayMove, rectSortingStrategy, SortableContext, sortableKeyboardCoordinates } from "@dnd-kit/sortable";
import {
  BadgePercent,
  Pencil,
  Plus,
  Power,
  PowerOff,
  ShieldCheck,
  SquarePlus,
  Trash2,
} from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { deletePlan, listPlans, type Plan, reorderPlans, updatePlan } from "@entities/plans/api";
import { useAnchorCurrency } from "@entities/pricing/use-anchor-currency";
import { usePermissions } from "@entities/user/use-current-user";
import { PlanAccessDialog } from "@features/plan-access/PlanAccessDialog";
import { PlanDiscountDialog } from "@features/plan-discount/PlanDiscountDialog";
import { PlanEditDialog } from "@features/plan-edit/PlanEditDialog";
import { getErrorMessage } from "@shared/api/http";
import { useEntityChanged } from "@shared/lib/entity-dialogs";
import { LoadGate, LoadGateHold } from "@shared/lib/load-gate";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { toast } from "@shared/lib/toast";
import type { ActionMenuItem } from "@shared/ui/ActionMenu";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { EmptyState, ErrorState } from "@shared/ui/glass/EmptyState";
import { PillTabs } from "@shared/ui/PillTabs";
import { Spinner } from "@shared/ui/Spinner";
import { Button } from "@shared/ui/Button";
import { Pressable } from "@shared/ui/Pressable";

import { PlanCard } from "./PlanCard";

type Filter = "all" | "active" | "inactive";

// On the grid wrapper so longer content can grow the card without clipping.
const CARD_HEIGHT_CLASSNAME = "aspect-[1.4]";

// the create card turns primary on hover, its icon too
function CreatePlanIcon({ className = "" }: { className?: string }) {
  return <SquarePlus className={`${className} transition-colors group-hover:text-primary`} />;
}

export function PlansPage() {
  const { t } = useTranslation();
  const [filter, setFilter] = useState<Filter>("all");
  const [editingPlan, setEditingPlan] = useState<Plan | null | "new">(null);
  const [accessPlan, setAccessPlan] = useState<Plan | null>(null);
  const [discountPlan, setDiscountPlan] = useState<Plan | null>(null);
  const [pendingDelete, setPendingDelete] = useState<Plan | null>(null);
  const sensors = useSensors(
    useSensor(MouseSensor, { activationConstraint: { distance: 8 } }),
    // long press: a plain swipe over the cards still scrolls the page
    useSensor(TouchSensor, { activationConstraint: { delay: 250, tolerance: 8 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const permissions = usePermissions();
  const canCreate = permissions.includes("PLANS_CREATE");
  const canUpdate = permissions.includes("PLANS_UPDATE");
  const canDelete = permissions.includes("PLANS_DELETE");
  const canManageAccess = permissions.includes("PLANS_ACCESS_MANAGE");
  const canManageDiscount = permissions.includes("PLANS_DISCOUNT_MANAGE");
  const canReorder = permissions.includes("PLANS_ORDER_MANAGE");
  // the dialog gates its fields, durations and squads by their own permissions
  const canEdit =
    canUpdate ||
    permissions.includes("PLANS_DURATIONS_MANAGE") ||
    (permissions.includes("PLANS_SQUADS_MANAGE") && permissions.includes("SUBSCRIPTIONS_PANEL_SQUADS_VIEW"));

  const [state, reload, setPlans] = useAsyncResource(listPlans);
  useEntityChanged("plan", reload);
  const anchorCurrency = useAnchorCurrency();

  const handleSaved = (plan: Plan) => {
    if (state.kind !== "ready") return;
    const exists = state.data.some((item) => item.id === plan.id);
    setPlans(exists ? state.data.map((item) => (item.id === plan.id ? plan : item)) : [...state.data, plan]);
  };

  const handleToggleActive = async (plan: Plan) => {
    if (state.kind !== "ready") return;
    const previous = state.data;
    setPlans(state.data.map((item) => (item.id === plan.id ? { ...item, is_active: !item.is_active } : item)));
    try {
      await updatePlan(plan.id, { is_active: !plan.is_active });
    } catch (err) {
      setPlans(previous);
      toast.error(getErrorMessage(err, t("plans.edit.error")));
    }
  };

  const handleDragEnd = async ({ active, over }: DragEndEvent) => {
    if (state.kind !== "ready" || !over || active.id === over.id) return;
    const from = state.data.findIndex((plan) => plan.id === active.id);
    const to = state.data.findIndex((plan) => plan.id === over.id);
    const previous = state.data;
    const reordered = arrayMove(state.data, from, to);
    setPlans(reordered);
    try {
      const result = await reorderPlans(reordered.map((plan) => plan.id));
      setPlans(result);
    } catch (err) {
      setPlans(previous);
      toast.error(getErrorMessage(err, t("plans.reorderError")));
    }
  };

  const handleDelete = async (plan: Plan) => {
    try {
      await deletePlan(plan.id);
      if (state.kind === "ready") {
        setPlans(state.data.filter((item) => item.id !== plan.id));
      }
    } catch (err) {
      toast.error(getErrorMessage(err, t("plans.delete.error")));
    }
  };

  const visibleItems =
    state.kind === "ready"
      ? state.data.filter((plan) => filter === "all" || plan.is_active === (filter === "active"))
      : [];
  // reordering a filtered subset has no well-defined position in the full list
  const isSortable = canReorder && filter === "all";

  const activeCount = state.kind === "ready" ? state.data.filter((plan) => plan.is_active).length : 0;
  const filterLabel = (key: Filter) => {
    const label = t(`plans.filters.${key}`);
    if (state.kind !== "ready") return label;
    const n = key === "all" ? state.data.length : key === "active" ? activeCount : state.data.length - activeCount;
    return `${label} · ${n}`;
  };

  return (
    // as the broadcasts page: the filter bar floats over a scroller of its own, whose fade clears the bar
    <div data-fills-main className="relative flex flex-1 flex-col md:min-h-0 md:pr-[var(--scrollbar-size)] md:-mb-5">
      <div className="glass-panel flex shrink-0 flex-wrap items-center gap-2 rounded-3xl p-1.5 md:absolute md:left-0 md:right-[var(--scrollbar-size)] md:top-0 md:z-10 md:flex-nowrap">
        <div className="min-w-0 flex-1 md:max-w-md">
          <PillTabs
            items={(["all", "active", "inactive"] as const).map((key) => ({ key, label: filterLabel(key) }))}
            activeKey={filter}
            onSelect={setFilter}
          />
        </div>
        {canCreate && (
          <Button variant="glassAccent" type="button" onClick={() => setEditingPlan("new")} className="md:ml-auto">
            <Plus className="size-4" />
            {t("plans.create.button")}
          </Button>
        )}
      </div>

      <div className="scroll-fade-y scroll-fade-gap page-scroll mt-1 pt-2 md:mt-0 md:min-h-0 md:flex-1 md:overflow-y-auto md:pt-[68px] md:scroll-pt-[68px] [--fade-rest-start:48px] [--fade-bottom-size:0px] [scrollbar-gutter:stable] max-md:[scrollbar-gutter:auto] max-md:[scrollbar-width:none] max-md:[&::-webkit-scrollbar]:hidden md:-mr-5 md:pb-5 md:pr-[calc(1.25rem-var(--scrollbar-size))]">
      <LoadGate>
      <LoadGateHold isLoading={state.kind === "loading"} />
      {state.kind === "loading" && <Spinner size="page" />}
      {state.kind === "error" && (
        <div className="glass-panel rounded-3xl p-4">
          <ErrorState text={t("common.loadError")} size="page" />
        </div>
      )}
      {state.kind === "ready" && visibleItems.length === 0 && !canCreate && (
        <div className="glass-panel rounded-3xl p-4">
          <EmptyState text={t(state.data.length === 0 ? "plans.empty" : "plans.noMatches")} size="page" />
        </div>
      )}
      {state.kind === "ready" && (visibleItems.length > 0 || canCreate) && (
        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={(e) => void handleDragEnd(e)}>
          <SortableContext items={visibleItems.map((plan) => plan.id)} strategy={rectSortingStrategy}>
            <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-3">
              {visibleItems.map((plan) => {
                const menuItems: ActionMenuItem[] = [];
                if (canEdit) {
                  menuItems.push({ label: t("common.edit"), icon: Pencil, onClick: () => setEditingPlan(plan) });
                }
                if (canUpdate) {
                  menuItems.push({
                    label: t(plan.is_active ? "plans.disable" : "plans.enable"),
                    icon: plan.is_active ? PowerOff : Power,
                    onClick: () => void handleToggleActive(plan),
                  });
                }
                if (canManageAccess) {
                  menuItems.push({
                    label: t("plans.access.button"),
                    icon: ShieldCheck,
                    onClick: () => setAccessPlan(plan),
                  });
                }
                if (canManageDiscount) {
                  menuItems.push({
                    label: t("plans.discount.button"),
                    icon: BadgePercent,
                    onClick: () => setDiscountPlan(plan),
                  });
                }
                if (canDelete) {
                  menuItems.push({
                    label: t("common.delete"),
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
                  />
                );
              })}
              {canCreate && (
                <Pressable
                  type="button"
                  onClick={() => setEditingPlan("new")}
                  className={`group flex flex-col items-center justify-center gap-3 rounded-3xl border border-dashed border-glass-border p-4 text-[13px] font-medium text-muted-foreground transition-colors hover:border-primary/40 hover:bg-accent hover:text-primary ${CARD_HEIGHT_CLASSNAME}`}
                >
                  <CreatePlanIcon className="size-5" />
                  {t("plans.create.button")}
                </Pressable>
              )}
            </div>
          </SortableContext>
        </DndContext>
      )}
      </LoadGate>
      </div>

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

      {discountPlan && (
        <PlanDiscountDialog plan={discountPlan} onClose={() => setDiscountPlan(null)} onSaved={handleSaved} />
      )}

      {pendingDelete && (
        <ConfirmDialog
          title={t("plans.delete.confirmTitle")}
          message={t("plans.delete.confirm", { name: pendingDelete.name })}
          confirmLabel={t("common.delete")}
          cancelLabel={t("common.cancel")}
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
