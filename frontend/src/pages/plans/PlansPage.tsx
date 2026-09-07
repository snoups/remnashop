import { AlertCircle, ChevronDown, ChevronUp, Inbox, Plus, ShieldCheck, Tag, Trash2 } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { deletePlan, listPlans, type Plan, reorderPlans, updatePlan } from "@entities/plans/api";
import { useCurrentUser } from "@entities/user/use-current-user";
import { PlanAccessDialog } from "@features/plan-access/PlanAccessDialog";
import { PlanEditDialog } from "@features/plan-edit/PlanEditDialog";
import { getErrorMessage } from "@shared/api/http";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { toast } from "@shared/lib/toast";
import { ActionMenu, type ActionMenuItem } from "@shared/ui/ActionMenu";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { Spinner } from "@shared/ui/Spinner";
import { Switch } from "@shared/ui/Switch";

type LoadState = { kind: "loading" } | { kind: "error" } | { kind: "ready"; items: Plan[] };

const TYPE_PILL_CLASSNAME = "border-border bg-white/[0.04] text-muted-foreground";

function formatLimit(value: number, unlimitedLabel: string): string {
  return value === 0 ? unlimitedLabel : `${value} GB`;
}

export function PlansPage() {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const [state, setState] = useState<LoadState>({ kind: "loading" });
  const [editingPlan, setEditingPlan] = useState<Plan | null | "new">(null);
  const [accessPlan, setAccessPlan] = useState<Plan | null>(null);
  const [pendingDelete, setPendingDelete] = useState<Plan | null>(null);

  const currentUserState = useCurrentUser();
  const permissions =
    currentUserState.kind === "ready" ? currentUserState.data.effective_permissions : [];
  const canCreate = permissions.includes("PLANS_CREATE");
  const canUpdate = permissions.includes("PLANS_UPDATE");
  const canDelete = permissions.includes("PLANS_DELETE");
  const canManageAccess = permissions.includes("PLANS_ACCESS_MANAGE");
  const canReorder = permissions.includes("PLANS_ORDER_MANAGE");

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

  const handleMove = async (index: number, direction: -1 | 1) => {
    if (state.kind !== "ready") return;
    const targetIndex = index + direction;
    if (targetIndex < 0 || targetIndex >= state.items.length) return;
    const reordered = [...state.items];
    [reordered[index], reordered[targetIndex]] = [reordered[targetIndex], reordered[index]];
    const previous = state.items;
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

  const unlimitedLabel = t("plans.unlimited");

  return (
    <div className="flex flex-col gap-4">
      <div className="relative rounded-2xl border border-white/[0.08] bg-white/[0.03] p-4">
        {state.kind === "loading" && <Spinner className="py-12" />}
        {state.kind === "error" && (
          <div className="flex flex-col items-center gap-2 py-12 text-error">
            <AlertCircle className="size-5" />
            <p className="text-sm">{t("plans.loadError")}</p>
          </div>
        )}
        {state.kind === "ready" && (
          <>
            <div className="mb-3 flex justify-end">
              {canCreate && (
                <motion.button
                  type="button"
                  onClick={() => setEditingPlan("new")}
                  {...bounceTap(bounceStrength)}
                  className="flex items-center gap-1.5 rounded-full bg-accent px-4 py-2 text-[13px] font-semibold text-primary transition-colors hover:bg-primary/20"
                >
                  <Plus className="size-3.5" />
                  {t("plans.create.button")}
                </motion.button>
              )}
            </div>

            {state.items.length === 0 && (
              <div className="flex flex-col items-center gap-2 py-12 text-muted-foreground">
                <Inbox className="size-5" />
                <p className="text-sm">{t("plans.empty")}</p>
              </div>
            )}

            {state.items.length > 0 && (
              <div className="flex flex-col divide-y divide-border/50">
                {state.items.map((plan, index) => {
                  const menuItems: ActionMenuItem[] = [];
                  if (canUpdate) {
                    menuItems.push({
                      label: t("plans.edit.button"),
                      icon: Tag,
                      onClick: () => setEditingPlan(plan),
                    });
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

                  const durationChips = plan.durations
                    .slice()
                    .sort((a, b) => a.order_index - b.order_index)
                    .map((d) => `${d.days}d`)
                    .join(" · ");

                  return (
                    <div
                      key={plan.id}
                      className="flex items-center justify-between gap-3 rounded-full px-3 py-2.5 [transition-property:background-color] duration-150 hover:bg-white/[0.04]"
                    >
                      <div className="flex min-w-0 items-center gap-2">
                        {canReorder && (
                          <div className="flex shrink-0 flex-col">
                            <button
                              type="button"
                              disabled={index === 0}
                              onClick={() => void handleMove(index, -1)}
                              className="flex size-5 items-center justify-center text-muted-foreground transition-colors hover:text-foreground disabled:cursor-not-allowed disabled:opacity-30"
                            >
                              <ChevronUp className="size-3.5" />
                            </button>
                            <button
                              type="button"
                              disabled={index === state.items.length - 1}
                              onClick={() => void handleMove(index, 1)}
                              className="flex size-5 items-center justify-center text-muted-foreground transition-colors hover:text-foreground disabled:cursor-not-allowed disabled:opacity-30"
                            >
                              <ChevronDown className="size-3.5" />
                            </button>
                          </div>
                        )}
                        <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-white/[0.06] text-foreground">
                          <Tag className="size-4" />
                        </div>
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <p className="truncate text-[13.5px] font-medium text-foreground">{plan.name}</p>
                            {plan.is_trial && (
                              <span className="shrink-0 rounded-full border border-warning/30 bg-warning/10 px-2 py-0.5 text-[10.5px] font-semibold uppercase tracking-wide text-warning">
                                {t("plans.edit.isTrialLabel")}
                              </span>
                            )}
                            {plan.tag && (
                              <span className="shrink-0 rounded-full border border-primary/40 bg-accent px-2 py-0.5 text-[10.5px] font-semibold uppercase tracking-wide text-primary">
                                {plan.tag}
                              </span>
                            )}
                          </div>
                          <p className="truncate font-mono text-[12px] text-muted-foreground">
                            {plan.public_code} &middot; {t(`plans.edit.type.${plan.type}`)} &middot;{" "}
                            {formatLimit(plan.traffic_limit, unlimitedLabel)} &middot;{" "}
                            {formatLimit(plan.device_limit, unlimitedLabel)}
                          </p>
                        </div>
                      </div>

                      <div className="flex shrink-0 items-center gap-3">
                        <span
                          className={`hidden shrink-0 rounded-full border px-2 py-0.5 text-[10.5px] font-semibold uppercase tracking-wide sm:inline-block ${TYPE_PILL_CLASSNAME}`}
                        >
                          {t(`plans.access.availability.${plan.availability}`)}
                        </span>
                        <span className="hidden text-[12px] text-muted-foreground md:inline">
                          {durationChips || "—"}
                        </span>
                        {canUpdate && (
                          <Switch
                            checked={plan.is_active}
                            onChange={() => void handleToggleActive(plan)}
                            ariaLabel={t("plans.edit.isActiveLabel")}
                          />
                        )}
                        {menuItems.length > 0 && <ActionMenu items={menuItems} />}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </>
        )}
      </div>

      {editingPlan !== null && (
        <PlanEditDialog
          plan={editingPlan === "new" ? null : editingPlan}
          onClose={() => setEditingPlan(null)}
          onSaved={handleSaved}
        />
      )}

      {accessPlan && (
        <PlanAccessDialog plan={accessPlan} onClose={() => setAccessPlan(null)} onSaved={handleSaved} />
      )}

      {pendingDelete && (
        <ConfirmDialog
          title={t("plans.delete.button")}
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
