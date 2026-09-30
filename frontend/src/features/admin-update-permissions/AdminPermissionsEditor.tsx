import { useMemo, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import type { Admin } from "@entities/admin/api";
import { updateAdmin } from "@entities/admin/api";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { PermissionPicker } from "@entities/admin/PermissionPicker";
import { usePermissionCatalog } from "@entities/admin/use-permission-catalog";
import type { Permission } from "@shared/types/rbac";
import { Button } from "@shared/ui/Button";

interface AdminPermissionsEditorProps {
  admin: Admin;
  onSaved: (admin: Admin) => void;
  onCancel: () => void;
  className?: string;
}

export function AdminPermissionsEditor({ admin, onSaved, onCancel, className = "" }: AdminPermissionsEditorProps) {
  const { t } = useTranslation();
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
      {/* 85vh = Modal's cap; 311px = AdminDetailsDialog's header, tabs, footer and this card's own chrome.
          -mt-2: the first h-11 row already insets its content 8px, so the card's top padding reads as its bottom one */}
      <div className="-mx-2 -mt-2 max-h-[calc(85vh-311px)] overflow-y-auto px-2">
        <PermissionPicker selected={selected} onToggle={toggle} baseline={roleDefaults} />
      </div>

      <div className="flex gap-2">
        <Button
          variant="outline"
          className="flex-1"
          type="button"
          onClick={onCancel}
        >
          {t("admins.permissionsForm.reset")}
        </Button>
        <Button
          variant="accent"
          className="flex-1"
          type="submit"
          disabled={isSubmitting}
        >
          {t("admins.permissionsForm.submit")}
        </Button>
      </div>
    </form>
  );
}
