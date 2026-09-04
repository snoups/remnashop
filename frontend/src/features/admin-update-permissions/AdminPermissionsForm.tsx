import { ShieldCheck, X } from "lucide-react";
import { motion } from "motion/react";
import { useReducer, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { type Admin, updateAdmin } from "@entities/admin/api";
import { getErrorMessage } from "@shared/api/http";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { toast } from "@shared/lib/toast";
import { Modal, useModalClose } from "@shared/ui/Modal";
import { PermissionPicker } from "@entities/admin/PermissionPicker";
import { Switch } from "@shared/ui/Switch";
import type { Permission } from "@shared/types/rbac";

interface AdminPermissionsFormProps {
  admin: Admin;
  /** Viewing your own permissions -- switches are shown but disabled, no submit. */
  readOnly?: boolean;
  onUpdated: () => void;
  onCancel: () => void;
}

interface PermissionsState {
  granted: Set<Permission>;
  revoked: Set<Permission>;
}

type PermissionsAction = { kind: "grant" | "revoke"; key: Permission };

// Grant and revoke are mutually exclusive for a given permission -- ticking
// one clears the other, instead of letting the operator create a
// contradictory state whose outcome (revoke wins, see PermissionPolicy)
// isn't visible in this UI. A single reducer (not two useState) because the
// resource-group pill dispatches for several distinct keys in one tick --
// with two independent useState calls, the cross-clear in each toggle would
// read the other's pre-batch value instead of what the earlier toggles in
// the same batch already did.
function permissionsReducer(state: PermissionsState, action: PermissionsAction): PermissionsState {
  const primary = action.kind === "grant" ? state.granted : state.revoked;
  const opposite = action.kind === "grant" ? state.revoked : state.granted;
  const nextPrimary = new Set(primary);
  const nextOpposite = new Set(opposite);

  if (nextPrimary.has(action.key)) {
    nextPrimary.delete(action.key);
  } else {
    nextPrimary.add(action.key);
    nextOpposite.delete(action.key);
  }

  return action.kind === "grant"
    ? { granted: nextPrimary, revoked: nextOpposite }
    : { granted: nextOpposite, revoked: nextPrimary };
}

export function AdminPermissionsForm({ admin, readOnly = false, onUpdated, onCancel }: AdminPermissionsFormProps) {
  return (
    <Modal onClose={onCancel} size="lg">
      <AdminPermissionsFormBody admin={admin} readOnly={readOnly} onUpdated={onUpdated} />
    </Modal>
  );
}

function AdminPermissionsFormBody({
  admin,
  readOnly = false,
  onUpdated,
}: Pick<AdminPermissionsFormProps, "admin" | "readOnly" | "onUpdated">) {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const close = useModalClose();
  const [{ granted, revoked }, dispatch] = useReducer(permissionsReducer, {
    granted: new Set(admin.permission_grants),
    revoked: new Set(admin.permission_revokes),
  });
  const [isSubmitting, setIsSubmitting] = useState(false);

  const toggleGrant = (key: Permission) => dispatch({ kind: "grant", key });
  const toggleRevoke = (key: Permission) => dispatch({ kind: "revoke", key });

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setIsSubmitting(true);
    try {
      await updateAdmin(admin.id, {
        permission_grants: Array.from(granted),
        permission_revokes: Array.from(revoked),
      });
      onUpdated();
    } catch (err) {
      toast.error(getErrorMessage(err, t("admins.permissionsForm.error")));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <>
      <div className="flex items-center justify-between border-b border-border px-5 py-4">
        <div className="flex items-center gap-2.5">
          <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] text-foreground backdrop-blur-md">
            <ShieldCheck className="size-4" />
          </div>
          <div>
            <h2 className="text-base font-bold text-foreground">{t("admins.permissionsForm.title")}</h2>
            <p className="mt-0.5 text-[12px] text-muted-foreground">{admin.name}</p>
          </div>
        </div>
        <button
          type="button"
          onClick={close}
          aria-label={t("profile.edit.close")}
          className="flex size-8 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-white/[0.06] hover:text-foreground"
        >
          <X className="size-4" />
        </button>
      </div>

      <form onSubmit={(event) => void handleSubmit(event)} className="flex flex-col">
        <div className="flex flex-col px-5">
          <div className="grid grid-cols-[1fr_auto_auto] items-center gap-3 py-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
            <span>{t("admins.permissionsForm.headers.permission")}</span>
            <span>{t("admins.permissionsForm.headers.grant")}</span>
            <span>{t("admins.permissionsForm.headers.revoke")}</span>
          </div>
          <div className="max-h-[50vh] overflow-y-auto">
            <PermissionPicker
              mode="grant-revoke"
              granted={granted}
              revoked={revoked}
              onToggleGrant={toggleGrant}
              onToggleRevoke={toggleRevoke}
              disabled={readOnly}
            />
            <div className="grid grid-cols-[1fr_auto_auto] items-center gap-3 py-2">
              <span className="text-[13px] text-foreground/90">{t("permissions.OWN_ACCOUNT_MANAGE")}</span>
              <Switch
                checked={granted.has("OWN_ACCOUNT_MANAGE")}
                onChange={() => toggleGrant("OWN_ACCOUNT_MANAGE")}
                disabled={readOnly}
                ariaLabel={`${t("admins.permissionsForm.headers.grant")}: ${t("permissions.OWN_ACCOUNT_MANAGE")}`}
              />
              <Switch
                checked={revoked.has("OWN_ACCOUNT_MANAGE")}
                onChange={() => toggleRevoke("OWN_ACCOUNT_MANAGE")}
                disabled={readOnly}
                ariaLabel={`${t("admins.permissionsForm.headers.revoke")}: ${t("permissions.OWN_ACCOUNT_MANAGE")}`}
              />
            </div>
          </div>
        </div>

        <div className="flex gap-2 px-5 pb-5 pt-4">
          {readOnly ? (
            <button
              type="button"
              onClick={close}
              className="flex-1 rounded-full border border-border px-4 py-2 text-sm font-medium text-foreground/80 transition-colors hover:bg-white/5"
            >
              {t("profile.edit.close")}
            </button>
          ) : (
            <>
              <button
                type="button"
                onClick={close}
                className="flex-1 rounded-full border border-border px-4 py-2 text-sm font-medium text-foreground/80 transition-colors hover:bg-white/5"
              >
                {t("admins.permissionsForm.cancel")}
              </button>
              <motion.button
                type="submit"
                disabled={isSubmitting}
                {...bounceTap(bounceStrength)}
                className="flex-1 rounded-full bg-accent px-4 py-2 text-sm font-medium text-primary transition-colors hover:bg-primary/20 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {t("admins.permissionsForm.submit")}
              </motion.button>
            </>
          )}
        </div>
      </form>
    </>
  );
}
