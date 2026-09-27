import { AlertCircle, Check, Copy, Filter, Gift, Inbox, Pencil, Plus, Ticket, Trash2 } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";

import { type AddOnListItem, listAddons } from "@entities/addons/api";
import { type Plan, listPlans } from "@entities/plans/api";
import { deletePromocode, listPromocodes, type Promocode, updatePromocode } from "@entities/promocodes/api";
import {
  describeReward,
  getPromocodeStatus,
  PROMOCODE_STATUS_BADGE_CLASSNAME,
  PROMOCODE_STATUSES,
  REWARD_TYPES,
} from "@entities/promocodes/display";
import { useCurrentUser } from "@entities/user/use-current-user";
import { PromocodeCreateDialog } from "@features/promocode-create/PromocodeCreateDialog";
import { PromocodeEditDialog } from "@features/promocode-edit/PromocodeEditDialog";
import { getErrorMessage } from "@shared/api/http";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { toast } from "@shared/lib/toast";
import { ActionMenu, type ActionMenuItem } from "@shared/ui/ActionMenu";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { SelectDropdown } from "@shared/ui/SelectDropdown";
import { Spinner } from "@shared/ui/Spinner";
import { Switch } from "@shared/ui/Switch";

type LoadState = { kind: "loading" } | { kind: "error" } | { kind: "ready"; items: Promocode[] };

const ROW_GRID_CLASSNAME = "grid grid-cols-[36px_minmax(0,1fr)_110px_110px_100px_76px] items-center gap-3";
const COPIED_RESET_MS = 1500;

export function PromocodesPage() {
  const { t, i18n } = useTranslation();
  const bounceStrength = useBounceStrength();
  const [state, setState] = useState<LoadState>({ kind: "loading" });
  const [addons, setAddons] = useState<AddOnListItem[]>([]);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [status, setStatus] = useState("");
  const [rewardType, setRewardType] = useState("");
  // set by the header search's deep link; no local search box
  const [searchParams] = useSearchParams();
  const search = (searchParams.get("search") ?? "").trim().toLowerCase();
  const [copiedId, setCopiedId] = useState<number | null>(null);
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

  const visibleItems = useMemo(
    () =>
      state.kind === "ready"
        ? state.items.filter(
            (promo) =>
              (!status || getPromocodeStatus(promo) === status) &&
              (!rewardType || promo.reward_type === rewardType) &&
              (!search || promo.code.toLowerCase().includes(search)),
          )
        : [],
    [state, status, rewardType, search],
  );

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

  const handleCopy = (promo: Promocode) => {
    navigator.clipboard?.writeText(promo.code).catch(() => {});
    setCopiedId(promo.id);
    setTimeout(() => setCopiedId((current) => (current === promo.id ? null : current)), COPIED_RESET_MS);
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <div className="w-48">
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
          <div className="w-56">
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
        </div>
        {canCreate && (
          <motion.button
            type="button"
            onClick={() => setIsCreateOpen(true)}
            {...bounceTap(bounceStrength)}
            className="flex items-center gap-1.5 rounded-full bg-accent px-4 py-2 text-sm font-medium text-primary transition-colors hover:bg-primary/20"
          >
            <Plus className="size-3.5" />
            {t("promocodes.create.button")}
          </motion.button>
        )}
      </div>

      <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-4">
        <div className="flex items-center gap-2.5">
          <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] text-foreground backdrop-blur-md">
            <Ticket className="size-4" />
          </div>
          <div className="min-w-0">
            <h2 className="flex items-center gap-2 text-sm font-bold text-foreground">
              {t("promocodes.title")}
              {state.kind === "ready" && (
                <span className="text-[11.5px] font-normal tabular-nums text-muted-foreground">
                  {state.items.length}
                </span>
              )}
            </h2>
            <p className="mt-0.5 text-[12.5px] text-muted-foreground">{t("promocodes.description")}</p>
          </div>
        </div>

        <div className="-mx-4 mt-4 border-t border-white/[0.07]" />

        {state.kind === "loading" && <Spinner className="py-12" />}
        {state.kind === "error" && (
          <div className="flex flex-col items-center gap-2 py-12 text-error">
            <AlertCircle className="size-5" />
            <p className="text-sm">{t("promocodes.loadError")}</p>
          </div>
        )}
        {state.kind === "ready" && visibleItems.length === 0 && (
          <div className="flex flex-col items-center gap-2 py-12 text-muted-foreground">
            <Inbox className="size-5" />
            <p className="text-sm">{t(state.items.length === 0 ? "promocodes.empty" : "promocodes.noMatches")}</p>
          </div>
        )}
        {state.kind === "ready" && visibleItems.length > 0 && (
          <div className="mt-3">
            <div
              className={`${ROW_GRID_CLASSNAME} mb-1 border-b border-border px-3 pb-2.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground`}
            >
              <span className="col-span-2">{t("promocodes.columns.code")}</span>
              <span>{t("promocodes.fields.activations")}</span>
              <span>{t("promocodes.fields.expires")}</span>
              <span>{t("promocodes.columns.status")}</span>
              <span />
            </div>
            <div className="flex flex-col divide-y divide-border/50">
              {visibleItems.map((promo) => {
                const promoStatus = getPromocodeStatus(promo);
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

                return (
                  <div
                    key={promo.id}
                    className={`${ROW_GRID_CLASSNAME} rounded-full px-3 py-2.5 [transition-property:background-color] duration-150 hover:bg-white/[0.04]`}
                  >
                    <span
                      aria-hidden
                      className={`flex size-9 items-center justify-center rounded-full ${
                        promoStatus === "ACTIVE" ? "bg-primary/10 text-primary" : "bg-white/[0.06] text-muted-foreground"
                      }`}
                    >
                      <Ticket className="size-4" />
                    </span>
                    <span className="min-w-0">
                      <span className="flex min-w-0 items-center gap-1.5">
                        <span className="truncate font-mono text-[13.5px] font-bold text-foreground">{promo.code}</span>
                        <button
                          type="button"
                          onClick={() => handleCopy(promo)}
                          aria-label={t("promocodes.copyAria", { code: promo.code })}
                          className="flex size-6 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-white/[0.08] hover:text-foreground"
                        >
                          {copiedId === promo.id ? (
                            <Check className="size-3 text-success" />
                          ) : (
                            <Copy className="size-3" />
                          )}
                        </button>
                        {promo.is_reusable && (
                          <span className="shrink-0 rounded-full border border-primary/40 bg-accent px-2 py-px text-[10.5px] font-semibold text-primary">
                            &infin;
                          </span>
                        )}
                      </span>
                      <span className="block truncate text-[12px] text-muted-foreground">
                        <span className="font-medium text-foreground/80">{describeReward(promo, addons, plans, t)}</span>
                        {" · "}
                        {t(`promocodes.availability.${promo.availability}`)}
                      </span>
                    </span>
                    <span className="text-[13px] tabular-nums text-foreground">
                      {promo.max_activations !== null
                        ? promo.max_activations
                        : t("promocodes.unlimitedActivations")}
                    </span>
                    <span className="text-[13px] tabular-nums text-foreground">
                      {promo.expires_at
                        ? new Date(promo.expires_at).toLocaleDateString(i18n.language, {
                            day: "numeric",
                            month: "short",
                            year: "numeric",
                          })
                        : t("promocodes.noExpiry")}
                    </span>
                    <span>
                      <span
                        className={`rounded-full border px-2 py-0.5 text-[10.5px] font-semibold uppercase tracking-wide ${PROMOCODE_STATUS_BADGE_CLASSNAME[promoStatus]}`}
                      >
                        {t(`promocodes.status.${promoStatus}`)}
                      </span>
                    </span>
                    <span className="flex items-center justify-end gap-1">
                      {canUpdate && (
                        <Switch
                          checked={promo.is_active}
                          onChange={() => void handleToggleActive(promo)}
                          ariaLabel={t("promocodes.edit.activeLabel")}
                        />
                      )}
                      {menuItems.length > 0 && <ActionMenu items={menuItems} />}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}
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

      {editingPromocode && (
        <PromocodeEditDialog
          promocode={editingPromocode}
          addons={addons}
          plans={plans}
          onDelete={
            canDelete
              ? () => {
                  setPendingDelete(editingPromocode);
                  setEditingPromocode(null);
                }
              : undefined
          }
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
