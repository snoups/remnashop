import { AlertCircle, Copy, Inbox, Pencil, Plus, Ticket, Trash2 } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { type AddOnListItem, listAddons } from "@entities/addons/api";
import { type Plan, listPlans } from "@entities/plans/api";
import { deletePromocode, listPromocodes, type Promocode, updatePromocode } from "@entities/promocodes/api";
import { useCurrentUser } from "@entities/user/use-current-user";
import { PromocodeCreateDialog } from "@features/promocode-create/PromocodeCreateDialog";
import { PromocodeEditDialog } from "@features/promocode-edit/PromocodeEditDialog";
import { getErrorMessage } from "@shared/api/http";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { toast } from "@shared/lib/toast";
import { ActionMenu, type ActionMenuItem } from "@shared/ui/ActionMenu";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { Spinner } from "@shared/ui/Spinner";
import { Switch } from "@shared/ui/Switch";

type LoadState = { kind: "loading" } | { kind: "error" } | { kind: "ready"; items: Promocode[] };
type TranslateFn = (key: string) => string;

function describeReward(promo: Promocode, addons: AddOnListItem[], plans: Plan[], t: TranslateFn): string {
  switch (promo.reward_type) {
    case "DURATION":
      return `+${promo.reward ?? 0}d`;
    case "TRAFFIC":
    case "DEVICES": {
      const addon = addons.find((a) => a.id === promo.reward_addon_id);
      return addon ? `+${addon.name}` : t(`promocodes.rewardType.${promo.reward_type}`);
    }
    case "SUBSCRIPTION": {
      const plan = plans.find((p) => p.id === promo.reward_plan_id);
      const planLabel = plan ? plan.name : t("promocodes.rewardType.SUBSCRIPTION");
      return `${planLabel} · ${promo.reward_duration_days ?? 0}d`;
    }
    case "PERSONAL_DISCOUNT":
    case "PURCHASE_DISCOUNT":
      return `-${promo.reward ?? 0}%`;
    default:
      return t(`promocodes.rewardType.${promo.reward_type}`);
  }
}

export function PromocodesPage() {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const [state, setState] = useState<LoadState>({ kind: "loading" });
  const [addons, setAddons] = useState<AddOnListItem[]>([]);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [editingPromocode, setEditingPromocode] = useState<Promocode | null>(null);
  const [pendingDelete, setPendingDelete] = useState<Promocode | null>(null);

  const currentUserState = useCurrentUser();
  const permissions =
    currentUserState.kind === "ready" ? currentUserState.data.effective_permissions : [];
  const canCreate = permissions.includes("PROMOCODES_CREATE");
  const canUpdate = permissions.includes("PROMOCODES_UPDATE");
  const canDelete = permissions.includes("PROMOCODES_DELETE");
  const canGenerateCode = permissions.includes("PROMOCODES_GENERATE_CODE");

  useEffect(() => {
    const controller = new AbortController();
    listPromocodes(controller.signal)
      .then((items) => {
        if (!controller.signal.aborted) setState({ kind: "ready", items });
      })
      .catch(() => {
        if (!controller.signal.aborted) setState({ kind: "error" });
      });
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

  const handleSaved = (promo: Promocode) => {
    if (state.kind !== "ready") return;
    const exists = state.items.some((item) => item.id === promo.id);
    setState({
      kind: "ready",
      items: exists ? state.items.map((item) => (item.id === promo.id ? promo : item)) : [promo, ...state.items],
    });
  };

  const handleToggleActive = async (promo: Promocode) => {
    if (state.kind !== "ready") return;
    const previous = state.items;
    setState({
      kind: "ready",
      items: state.items.map((item) => (item.id === promo.id ? { ...item, is_active: !item.is_active } : item)),
    });
    try {
      await updatePromocode(promo.id, { is_active: !promo.is_active });
    } catch (err) {
      setState({ kind: "ready", items: previous });
      toast.error(getErrorMessage(err, t("promocodes.edit.error")));
    }
  };

  const handleDelete = async (promo: Promocode) => {
    try {
      await deletePromocode(promo.id);
      if (state.kind === "ready") {
        setState({ kind: "ready", items: state.items.filter((item) => item.id !== promo.id) });
      }
    } catch (err) {
      toast.error(getErrorMessage(err, t("promocodes.delete.error")));
    }
  };

  const handleCopy = (code: string) => {
    navigator.clipboard?.writeText(code).catch(() => {});
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="relative rounded-2xl border border-white/[0.08] bg-white/[0.03] p-4">
        {state.kind === "loading" && <Spinner className="py-12" />}
        {state.kind === "error" && (
          <div className="flex flex-col items-center gap-2 py-12 text-error">
            <AlertCircle className="size-5" />
            <p className="text-sm">{t("promocodes.loadError")}</p>
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
                  {t("promocodes.create.button")}
                </motion.button>
              )}
            </div>

            {state.items.length === 0 && (
              <div className="flex flex-col items-center gap-2 py-12 text-muted-foreground">
                <Inbox className="size-5" />
                <p className="text-sm">{t("promocodes.empty")}</p>
              </div>
            )}

            {state.items.length > 0 && (
              <div className="flex flex-col divide-y divide-border/50">
                {state.items.map((promo) => {
                  const menuItems: ActionMenuItem[] = [];
                  if (canUpdate) {
                    menuItems.push({
                      label: t("promocodes.edit.button"),
                      icon: Pencil,
                      onClick: () => setEditingPromocode(promo),
                    });
                  }
                  if (canDelete) {
                    menuItems.push({
                      label: t("promocodes.delete.button"),
                      icon: Trash2,
                      variant: "danger",
                      onClick: () => setPendingDelete(promo),
                    });
                  }

                  const activations = promo.max_activations !== null
                    ? String(promo.max_activations)
                    : t("promocodes.unlimitedActivations");
                  const expires = promo.expires_at
                    ? new Date(promo.expires_at).toLocaleDateString()
                    : t("promocodes.noExpiry");

                  return (
                    <div
                      key={promo.id}
                      className="flex items-center justify-between gap-3 rounded-full px-3 py-2.5 [transition-property:background-color] duration-150 hover:bg-white/[0.04]"
                    >
                      <div className="flex min-w-0 items-center gap-3">
                        <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-white/[0.06] text-foreground">
                          <Ticket className="size-4" />
                        </div>
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <p className="truncate font-mono text-[13.5px] font-bold text-foreground">{promo.code}</p>
                            <button
                              type="button"
                              onClick={() => handleCopy(promo.code)}
                              aria-label={promo.code}
                              className="text-muted-foreground transition-colors hover:text-foreground"
                            >
                              <Copy className="size-3" />
                            </button>
                            <span className="shrink-0 rounded-full border border-border bg-white/[0.04] px-2 py-0.5 text-[10.5px] font-semibold uppercase tracking-wide text-muted-foreground">
                              {t(`promocodes.availability.${promo.availability}`)}
                            </span>
                            {promo.is_reusable && (
                              <span className="shrink-0 rounded-full border border-primary/40 bg-accent px-2 py-0.5 text-[10.5px] font-semibold uppercase tracking-wide text-primary">
                                &infin;
                              </span>
                            )}
                          </div>
                          <p className="truncate text-[12px] text-muted-foreground">
                            {describeReward(promo, addons, plans, t)}
                          </p>
                        </div>
                      </div>

                      <div className="flex shrink-0 items-center gap-4">
                        <div className="text-right">
                          <p className="text-[11px] text-muted-foreground">{t("promocodes.fields.activations")}</p>
                          <p className="text-[13px] font-medium text-foreground">{activations}</p>
                        </div>
                        <div className="text-right">
                          <p className="text-[11px] text-muted-foreground">{t("promocodes.fields.expires")}</p>
                          <p className="text-[13px] font-medium text-foreground">{expires}</p>
                        </div>
                        {canUpdate && (
                          <Switch
                            checked={promo.is_active}
                            onChange={() => void handleToggleActive(promo)}
                            ariaLabel={t("promocodes.edit.activeLabel")}
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

      {isCreateOpen && (
        <PromocodeCreateDialog
          canGenerateCode={canGenerateCode}
          onClose={() => setIsCreateOpen(false)}
          onSaved={handleSaved}
        />
      )}

      {editingPromocode && (
        <PromocodeEditDialog
          promocode={editingPromocode}
          onClose={() => setEditingPromocode(null)}
          onSaved={handleSaved}
        />
      )}

      {pendingDelete && (
        <ConfirmDialog
          title={t("promocodes.delete.button")}
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
