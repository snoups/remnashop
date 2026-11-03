import { useMemo, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import type { Admin } from "@entities/admin/api";
import { updateAdmin } from "@entities/admin/api";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { PermissionPicker } from "@entities/admin/PermissionPicker";
import { usePermissionCatalog } from "@entities/admin/use-permission-catalog";
import type { Permission } from "@shared/types/rbac";

// the dialog footer's save button submits this form via form=
export const ADMIN_PERMISSIONS_FORM_ID = "admin-permissions-form";

interface AdminPermissionsEditorProps {
  admin: Admin;
  onSaved: (admin: Admin) => void;
  /** the footer's save button disables itself while a save is in flight */
  onSubmittingChange: (isSubmitting: boolean) => void;
}

export function AdminPermissionsEditor({ admin, onSaved, onSubmittingChange }: AdminPermissionsEditorProps) {
  const { t } = useTranslation();
  const catalogState = usePermissionCatalog();
  const roleDefaults = useMemo(() => new Set(admin.role_permissions), [admin.role_permissions]);
  const [selected, setSelected] = useState(() => new Set(admin.effective_permissions));

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
    onSubmittingChange(true);
    try {
      const updated = await updateAdmin(admin.id, {
        permission_grants: grantable.filter((p) => selected.has(p) && !roleDefaults.has(p)),
        permission_revokes: grantable.filter((p) => !selected.has(p) && roleDefaults.has(p)),
      });
      onSaved(updated);
    } catch (err) {
      toast.error(getErrorMessage(err, t("admins.permissionsForm.error")));
    } finally {
      onSubmittingChange(false);
    }
  };

  return (
    <form id={ADMIN_PERMISSIONS_FORM_ID} onSubmit={(event) => void handleSubmit(event)}>
      <PermissionPicker selected={selected} onToggle={toggle} baseline={roleDefaults} />
    </form>
  );
}
