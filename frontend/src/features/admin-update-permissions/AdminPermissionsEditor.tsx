import { motion } from "motion/react";
import { useMemo, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import type { Admin } from "@entities/admin/api";
import { updateAdmin } from "@entities/admin/api";
import { getErrorMessage } from "@shared/api/http";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { toast } from "@shared/lib/toast";
import { PermissionPicker } from "@entities/admin/PermissionPicker";
import { usePermissionCatalog } from "@entities/admin/use-permission-catalog";
import type { Permission } from "@shared/types/rbac";

interface AdminPermissionsEditorProps {
  admin: Admin;
  onSaved: (admin: Admin) => void;
  onCancel: () => void;
  className?: string;
}

export function AdminPermissionsEditor({ admin, onSaved, onCancel, className = "" }: AdminPermissionsEditorProps) {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const catalogState = usePermissionCatalog();
  const roleDefaults = useMemo(() => new Set(admin.role_permissions), [admin.role_permissions]);
  const [selected, setSelected] = useState(() => new Set(admin.effective_permissions));
  const [isSubmitting, setIsSubmitting] = useState(false);

  // functional update: a kind pill toggles several keys in one tick
  const toggle = (permission: Permission) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(permission)) {
        next.delete(permission);
      } else {
        next.add(permission);
      }
      return next;
    });

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (catalogState.kind !== "ready") return;
    // overrides are just the diff against the role, limited to what the catalog lets an owner touch
    const grantable = catalogState.data.map((entry) => entry.permission);
    setIsSubmitting(true);
    try {
      const updated = await updateAdmin(admin.id, {
        permission_grants: grantable.filter((p) => selected.has(p) && !roleDefaults.has(p)),
        permission_revokes: grantable.filter((p) => !selected.has(p) && roleDefaults.has(p)),
      });
      onSaved(updated);
    } catch (err) {
      toast.error(getErrorMessage(err, t("admins.permissionsForm.error")));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <form onSubmit={(event) => void handleSubmit(event)} className={`flex flex-col gap-4 ${className}`}>
      <div className="-mx-2 max-h-[50vh] overflow-y-auto px-2">
        <PermissionPicker selected={selected} onToggle={toggle} baseline={roleDefaults} />
      </div>

      <div className="flex gap-2">
        <button
          type="button"
          onClick={onCancel}
          className="flex-1 rounded-full border border-border px-4 py-2 text-sm font-medium text-foreground/80 transition-colors hover:bg-white/5"
        >
          {t("admins.permissionsForm.reset")}
        </button>
        <motion.button
          type="submit"
          disabled={isSubmitting}
          {...bounceTap(bounceStrength)}
          className="flex-1 rounded-full bg-accent px-4 py-2 text-sm font-medium text-primary transition-colors hover:bg-primary/20 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {t("admins.permissionsForm.submit")}
        </motion.button>
      </div>
    </form>
  );
}
