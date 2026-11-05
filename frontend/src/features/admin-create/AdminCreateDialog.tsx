import { ShieldPlus } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { createAdmin } from "@entities/admin/api";
import { PermissionPicker } from "@entities/admin/PermissionPicker";
import { usePermissionCatalog } from "@entities/admin/use-permission-catalog";
import { getErrorMessage } from "@shared/api/http";
import { LOGIN_PATTERN } from "@shared/lib/login-validation";
import { toast } from "@shared/lib/toast";
import { Modal } from "@shared/ui/Modal";
import { useModalClose } from "@shared/ui/modal-hooks";
import { Button } from "@shared/ui/Button";
import { GLASS_DIALOG_BODY_CLASS, GLASS_DIALOG_CARD_CLASS, GLASS_DIALOG_FOOTER_CLASS } from "@shared/ui/classes";
import { DialogHeader } from "@shared/ui/glass/DialogHeader";
import { Field } from "@shared/ui/glass/Field";
import { Input } from "@shared/ui/glass/Input";
import type { Permission } from "@shared/types/rbac";

interface AdminCreateDialogProps {
  onCreated: (password: string) => void;
  onClose: () => void;
}

export function AdminCreateDialog({ onCreated, onClose }: AdminCreateDialogProps) {
  return (
    <Modal onClose={onClose} size="lg" scrollable>
      <AdminCreateFormBody onCreated={onCreated} />
    </Modal>
  );
}

function AdminCreateFormBody({ onCreated }: Pick<AdminCreateDialogProps, "onCreated">) {
  const { t } = useTranslation();
  const close = useModalClose();
  const [login, setLogin] = useState("");
  const [name, setName] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const catalogState = usePermissionCatalog();
  // null until touched: the picker starts from the ADMIN role defaults once the catalog is in
  const [picked, setPicked] = useState<Set<Permission> | null>(null);
  const roleDefaults = new Set(
    catalogState.kind === "ready"
      ? catalogState.data.filter((entry) => entry.admin_default).map((entry) => entry.permission)
      : [],
  );
  const selected = picked ?? roleDefaults;
  const isLoginInvalid = login.trim() !== "" && !LOGIN_PATTERN.test(login.trim());

  // functional update: a kind pill toggles several keys in one tick
  const toggle = (permission: Permission) =>
    setPicked((prev) => {
      const next = new Set(prev ?? roleDefaults);
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
    const grantable = catalogState.data.map((entry) => entry.permission);
    setIsSubmitting(true);
    try {
      const { password } = await createAdmin({
        login: login.trim(),
        name: name.trim(),
        permission_grants: grantable.filter((p) => selected.has(p) && !roleDefaults.has(p)),
        permission_revokes: grantable.filter((p) => !selected.has(p) && roleDefaults.has(p)),
      });
      close();
      onCreated(password);
    } catch (err) {
      toast.error(getErrorMessage(err, t("admins.create.error")));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <>
      <DialogHeader icon={ShieldPlus} title={t("admins.create.title")} />

      <form onSubmit={(event) => void handleSubmit(event)} className="flex min-h-0 flex-1 flex-col">
        <div className={`${GLASS_DIALOG_BODY_CLASS} flex flex-col gap-3`}>
          <div className={GLASS_DIALOG_CARD_CLASS}>
            <Field
              label={t("admins.create.loginLabel")}
              htmlFor="admin-create-login"
              required
              error={isLoginInvalid ? t("auth.errors.loginInvalidChars") : undefined}
            >
              <Input
                id="admin-create-login"
                value={login}
                onChange={(event) => setLogin(event.target.value)}
                placeholder={t("admins.create.loginPlaceholder")}
                aria-invalid={isLoginInvalid}
              />
            </Field>
            <Field label={t("admins.create.nameLabel")} htmlFor="admin-create-name" required>
              <Input
                id="admin-create-name"
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder={t("admins.create.namePlaceholder")}
              />
            </Field>
          </div>

          <div className={GLASS_DIALOG_CARD_CLASS}>
            <Field label={t("admins.create.permissionsLabel")}>
              <PermissionPicker selected={selected} onToggle={toggle} baseline={roleDefaults} />
            </Field>
          </div>
        </div>

        <div className={`${GLASS_DIALOG_FOOTER_CLASS} shrink-0 justify-end`}>
          <Button variant="glass" type="button" onClick={close}>
            {t("common.cancel")}
          </Button>
          <Button
            variant="glassAccent"
            type="submit"
            isLoading={isSubmitting}
            disabled={isLoginInvalid || catalogState.kind !== "ready"}
          >
            {t("common.create")}
          </Button>
        </div>
      </form>
    </>
  );
}
