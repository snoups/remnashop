import { UserPlus, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { createAdmin } from "@entities/admin/api";
import { getErrorMessage } from "@shared/api/http";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { toast } from "@shared/lib/toast";
import { DialogPortal } from "@shared/ui/DialogPortal";

interface AdminCreateFormProps {
  onCreated: (password: string) => void;
}

export function AdminCreateForm({ onCreated }: AdminCreateFormProps) {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const [login, setLogin] = useState("");
  const [name, setName] = useState("");
  const [isOpen, setIsOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleClose = () => {
    setIsOpen(false);
    setLogin("");
    setName("");
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setIsSubmitting(true);
    try {
      const { password } = await createAdmin({
        login,
        name,
        permission_grants: [],
        permission_revokes: [],
      });
      handleClose();
      onCreated(password);
    } catch (err) {
      toast.error(getErrorMessage(err, t("admins.create.error")));
    } finally {
      setIsSubmitting(false);
    }
  };

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

      <DialogPortal>
      <AnimatePresence>
        {isOpen && (
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
              onClick={handleClose}
            />

            <motion.div
              initial={{ opacity: 0, scale: 0.94, y: 8 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.94, y: 8 }}
              transition={{ duration: 0.18, ease: "easeOut" }}
              className="relative z-50 w-full max-w-sm rounded-dialog border border-white/[0.14] bg-popover/60 shadow-[0_24px_48px_-20px_rgba(4,8,20,0.6),inset_0_1px_0_rgba(232,236,251,0.16)] backdrop-blur-2xl backdrop-saturate-150"
            >
              <div className="flex items-center justify-between border-b border-border px-5 py-4">
                <h2 className="flex items-center gap-2.5 text-base font-bold text-foreground">
                  <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] text-foreground backdrop-blur-md">
                    <UserPlus className="size-4" />
                  </div>
                  {t("admins.create.title")}
                </h2>
                <button
                  type="button"
                  onClick={handleClose}
                  aria-label={t("profile.edit.close")}
                  className="flex size-8 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-white/[0.06] hover:text-foreground"
                >
                  <X className="size-4" />
                </button>
              </div>

              <form
                onSubmit={(event) => void handleSubmit(event)}
                className="flex flex-col gap-4 px-5 pb-5 pt-4"
              >
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
                    onClick={handleClose}
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
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
      </DialogPortal>
    </>
  );
}
