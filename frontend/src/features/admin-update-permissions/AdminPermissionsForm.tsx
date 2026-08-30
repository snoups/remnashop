import { ShieldCheck, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { type Admin, updateAdmin } from "@entities/admin/api";
import { getErrorMessage } from "@shared/api/http";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { toast } from "@shared/lib/toast";
import { DialogPortal } from "@shared/ui/DialogPortal";
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

export function AdminPermissionsForm({ admin, readOnly = false, onUpdated, onCancel }: AdminPermissionsFormProps) {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const [granted, setGranted] = useState<Set<Permission>>(new Set(admin.permission_grants));
  const [revoked, setRevoked] = useState<Set<Permission>>(new Set(admin.permission_revokes));
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Grant and revoke are mutually exclusive for a given permission -- ticking
  // one clears the other, instead of letting the operator create a
  // contradictory state whose outcome (revoke wins, see PermissionPolicy)
  // isn't visible in this UI. setGranted/setRevoked use the functional
  // updater form since the resource-group pill calls these for several
  // distinct keys in one tick -- reading `granted`/`revoked` directly would
  // make every call in that batch overwrite the previous one's result.
  const toggleGrant = (key: Permission) => {
    const isCurrentlyGranted = granted.has(key);
    setGranted((prev) => {
      const next = new Set(prev);
      if (isCurrentlyGranted) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
    if (!isCurrentlyGranted && revoked.has(key)) {
      setRevoked((prev) => {
        const next = new Set(prev);
        next.delete(key);
        return next;
      });
    }
  };

  const toggleRevoke = (key: Permission) => {
    const isCurrentlyRevoked = revoked.has(key);
    setRevoked((prev) => {
      const next = new Set(prev);
      if (isCurrentlyRevoked) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
    if (!isCurrentlyRevoked && granted.has(key)) {
      setGranted((prev) => {
        const next = new Set(prev);
        next.delete(key);
        return next;
      });
    }
  };

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
    <DialogPortal>
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.15, ease: "easeOut" }}
        className="fixed inset-0 z-40 flex items-center justify-center bg-black/55 backdrop-blur-3xl p-4"
      >
        <button
          type="button"
          aria-hidden
          tabIndex={-1}
          className="absolute inset-0 cursor-default"
          onClick={onCancel}
        />

        <motion.div
          initial={{ opacity: 0, scale: 0.94, y: 8 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.94, y: 8 }}
          transition={{ duration: 0.18, ease: "easeOut" }}
          className="relative z-50 w-full max-w-lg rounded-dialog border border-white/[0.14] bg-popover/60 shadow-[0_24px_48px_-20px_rgba(4,8,20,0.6),inset_0_1px_0_rgba(232,236,251,0.16)] backdrop-blur-2xl backdrop-saturate-150"
        >
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
              onClick={onCancel}
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
                  onClick={onCancel}
                  className="flex-1 rounded-full border border-border px-4 py-2 text-sm font-medium text-foreground/80 transition-colors hover:bg-white/5"
                >
                  {t("profile.edit.close")}
                </button>
              ) : (
                <>
                  <button
                    type="button"
                    onClick={onCancel}
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
        </motion.div>
      </motion.div>
    </AnimatePresence>
    </DialogPortal>
  );
}
