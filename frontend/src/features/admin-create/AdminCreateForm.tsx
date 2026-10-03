import { ShieldPlus } from "lucide-react";
import { motion } from "motion/react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { createAdmin } from "@entities/admin/api";
import { PermissionPicker } from "@entities/admin/PermissionPicker";
import { usePermissionCatalog } from "@entities/admin/use-permission-catalog";
import { getErrorMessage } from "@shared/api/http";
import { bounceTap } from "@shared/lib/bounceState";
import { LOGIN_PATTERN } from "@shared/lib/login-validation";
import { toast } from "@shared/lib/toast";
import { Modal } from "@shared/ui/Modal";
import { useModalClose } from "@shared/ui/modal-hooks";
import { Button } from "@shared/ui/Button";
import { DialogHeader } from "@shared/ui/DialogHeader";
import { TextInput } from "@shared/ui/TextInput";
import { Card } from "@shared/ui/Card";
import { Field } from "@shared/ui/Field";
import type { Permission } from "@shared/types/rbac";

const labelClassName = "text-sm font-medium text-foreground/80";

interface AdminCreateFormProps {
  onCreated: (password: string) => void;
}

export function AdminCreateForm({ onCreated }: AdminCreateFormProps) {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);

  return (
    <>
      <motion.button
        type="button"
        onClick={() => setIsOpen(true)}
        {...bounceTap(0.03)}
        className="group mb-2 flex w-full items-center gap-3 rounded-full border border-dashed border-white/[0.12] h-15 px-3 text-[13.5px] font-medium text-muted-foreground transition-colors hover:border-primary/40 hover:bg-accent hover:text-primary"
      >
        <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-white/[0.06] transition-colors group-hover:bg-transparent">
          <ShieldPlus className="size-4" />
        </span>
        {t("admins.create.button")}
      </motion.button>

      {isOpen && (
        <Modal onClose={() => setIsOpen(false)} size="lg" scrollable>
          <AdminCreateFormBody onCreated={onCreated} />
        </Modal>
      )}
    </>
  );
}

function AdminCreateFormBody({ onCreated }: AdminCreateFormProps) {
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
        <div className="scroll-fade-y flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto p-4">
          <Card variant="form">
            <Field
              label={t("admins.create.loginLabel")}
              htmlFor="admin-create-login"
              required
              error={isLoginInvalid ? t("auth.errors.loginInvalidChars") : undefined}
            >
              <TextInput
                id="admin-create-login"
                value={login}
                onChange={(event) => setLogin(event.target.value)}
                placeholder={t("admins.create.loginLabel")}
                required
                aria-invalid={isLoginInvalid}
              />
            </Field>
            <Field label={t("admins.create.nameLabel")} htmlFor="admin-create-name" required>
              <TextInput
                id="admin-create-name"
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder={t("admins.create.nameLabel")}
                required
              />
            </Field>
          </Card>

          <Card variant="form">
            <span className={labelClassName}>{t("admins.create.permissionsLabel")}</span>
            <PermissionPicker selected={selected} onToggle={toggle} baseline={roleDefaults} />
          </Card>
        </div>

        <div className="flex shrink-0 justify-end gap-2 border-t border-white/[0.07] px-5 py-4">
          <Button variant="outline" type="button" onClick={close}>
            {t("common.cancel")}
          </Button>
          <Button
            variant="accent"
            type="submit"
            disabled={isSubmitting || isLoginInvalid || catalogState.kind !== "ready"}
          >
            {t("common.create")}
          </Button>
        </div>
      </form>
    </>
  );
}
