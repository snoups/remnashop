import { UserPlus, X } from "lucide-react";
import { motion } from "motion/react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { createAdmin } from "@entities/admin/api";
import { getErrorMessage } from "@shared/api/http";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { toast } from "@shared/lib/toast";
import { Modal, useModalClose } from "@shared/ui/Modal";

interface AdminCreateFormProps {
  onCreated: (password: string) => void;
}

export function AdminCreateForm({ onCreated }: AdminCreateFormProps) {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const [isOpen, setIsOpen] = useState(false);

  return (
    <>
      <motion.button
        type="button"
        onClick={() => setIsOpen(true)}
        {...bounceTap(bounceStrength)}
        className="flex items-center gap-2 rounded-full border border-border px-3.5 py-2 text-sm font-medium text-foreground/90 transition-colors hover:bg-white/5"
      >
        <UserPlus className="size-4" />
        {t("admins.create.button")}
      </motion.button>

      {isOpen && (
        <Modal onClose={() => setIsOpen(false)} size="sm">
          <AdminCreateFormBody onCreated={onCreated} />
        </Modal>
      )}
    </>
  );
}

function AdminCreateFormBody({ onCreated }: AdminCreateFormProps) {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const close = useModalClose();
  const [login, setLogin] = useState("");
  const [name, setName] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setIsSubmitting(true);
    try {
      const { password } = await createAdmin({
        login: login.trim(),
        name: name.trim(),
        permission_grants: [],
        permission_revokes: [],
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
      <div className="flex items-center justify-between border-b border-border px-5 py-4">
        <h2 className="flex items-center gap-2.5 text-base font-bold text-foreground">
          <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] text-foreground backdrop-blur-md">
            <UserPlus className="size-4" />
          </div>
          {t("admins.create.title")}
        </h2>
        <button
          type="button"
          onClick={close}
          aria-label={t("profile.edit.close")}
          className="flex size-8 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-white/[0.06] hover:text-foreground"
        >
          <X className="size-4" />
        </button>
      </div>

      <form onSubmit={(event) => void handleSubmit(event)} className="flex flex-col gap-4 px-5 pb-5 pt-4">
        <div className="flex flex-col gap-1">
          <label htmlFor="admin-create-login" className="text-sm font-medium text-foreground/80">
            {t("admins.create.loginLabel")}
          </label>
          <input
            id="admin-create-login"
            value={login}
            onChange={(event) => setLogin(event.target.value)}
            placeholder={t("admins.create.loginLabel")}
            required
            pattern="[A-Za-z0-9._-]+"
            title={t("auth.errors.loginInvalidChars")}
            className="rounded-xl border border-border bg-input/60 px-3 py-2 text-sm text-foreground outline-none focus:border-primary"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor="admin-create-name" className="text-sm font-medium text-foreground/80">
            {t("admins.create.nameLabel")}
          </label>
          <input
            id="admin-create-name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder={t("admins.create.nameLabel")}
            required
            className="rounded-xl border border-border bg-input/60 px-3 py-2 text-sm text-foreground outline-none focus:border-primary"
          />
        </div>

        <div className="flex gap-2">
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
            {t("admins.create.submit")}
          </motion.button>
        </div>
      </form>
    </>
  );
}
