import { ChevronDown, Eye, EyeOff, Pencil, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, useState, type ChangeEvent, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { updateOwnProfile } from "@entities/user/api";
import { getErrorMessage } from "@shared/api/http";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { PASSWORD_PATTERN } from "@shared/lib/password-validation";
import { toast } from "@shared/lib/toast";
import { useReloadCurrentUser } from "@entities/user/use-current-user";
import { FieldHint } from "@shared/ui/FieldHint";
import { Modal, useModalClose } from "@shared/ui/Modal";

interface EditProfileDialogProps {
  name: string;
  login: string | null;
}

export function EditProfileDialog({ name, login }: EditProfileDialogProps) {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const [isOpen, setIsOpen] = useState(false);

  return (
    <>
      <motion.button
        type="button"
        onClick={() => setIsOpen(true)}
        {...bounceTap(bounceStrength)}
        className="flex shrink-0 items-center gap-2 rounded-full border border-border px-3 py-1.5 text-[12px] font-semibold text-foreground/90 transition-colors hover:bg-white/5"
      >
        <Pencil className="size-3.5" />
        {t("profile.edit.button")}
      </motion.button>

      {isOpen && (
        <Modal onClose={() => setIsOpen(false)} size="sm">
          <EditProfileDialogBody name={name} login={login} />
        </Modal>
      )}
    </>
  );
}

function EditProfileDialogBody({ name, login }: EditProfileDialogProps) {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const close = useModalClose();
  const reloadCurrentUser = useReloadCurrentUser();
  const [isPasswordOpen, setIsPasswordOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [nameValue, setNameValue] = useState(name);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showCurrentPassword, setShowCurrentPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [avatarPreview, setAvatarPreview] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const initials = (login ?? "?").slice(0, 2).toUpperCase();

  // Revokes on unmount too, not just on the next pick -- otherwise a picked
  // preview outlives the dialog for as long as the tab stays open.
  useEffect(() => {
    return () => {
      if (avatarPreview) URL.revokeObjectURL(avatarPreview);
    };
  }, [avatarPreview]);

  const handleAvatarPick = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    // The unmount/change effect above revokes whatever this replaces.
    setAvatarPreview(URL.createObjectURL(file));
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();

    if (newPassword && !currentPassword) {
      toast.error(t("profile.edit.currentPasswordRequired"));
      return;
    }

    if (newPassword && !PASSWORD_PATTERN.test(newPassword)) {
      toast.error(t("auth.errors.passwordRequirements"));
      return;
    }

    if (newPassword && newPassword !== confirmPassword) {
      toast.error(t("auth.errors.passwordsDoNotMatch"));
      return;
    }

    setIsSubmitting(true);
    try {
      await updateOwnProfile({
        name: nameValue !== name ? nameValue : undefined,
        current_password: newPassword ? currentPassword : undefined,
        new_password: newPassword || undefined,
      });
      reloadCurrentUser();
      toast.success(t("profile.edit.saved"));
      close();
    } catch (err) {
      toast.error(getErrorMessage(err, t("auth.errors.genericError")));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <>
      <div className="flex items-center justify-between border-b border-border px-5 py-4">
        <h2 className="flex items-center gap-2.5 text-base font-bold text-foreground">
          <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] text-foreground backdrop-blur-md">
            <Pencil className="size-4" />
          </div>
          {t("profile.edit.title")}
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
        <div className="flex items-center gap-4">
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            aria-label={t("profile.edit.changeAvatar")}
            className="group relative shrink-0"
          >
            <div className="flex size-14 items-center justify-center overflow-hidden rounded-full bg-foreground text-[18px] font-bold text-canvas">
              {avatarPreview ? <img src={avatarPreview} alt="" className="size-full object-cover" /> : initials}
            </div>
            <span className="absolute -bottom-1 -right-1 z-10 flex size-6 items-center justify-center rounded-full border border-glass-border bg-surface text-foreground transition-colors group-hover:border-primary group-hover:text-primary">
              <Pencil className="size-3.5" />
            </span>
          </button>
          <input ref={fileInputRef} type="file" accept="image/*" onChange={handleAvatarPick} className="hidden" />
          <p className="text-[12px] text-muted-foreground">{t("profile.edit.avatarHint")}</p>
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="edit-name" className="text-sm font-medium text-foreground/80">
            {t("profile.edit.nameLabel")}
          </label>
          <input
            id="edit-name"
            value={nameValue}
            onChange={(event) => setNameValue(event.target.value)}
            className="rounded-xl border border-border bg-input/60 px-3 py-2 text-sm text-foreground outline-none focus:border-primary"
          />
        </div>

        <div>
          <motion.button
            type="button"
            onClick={() => setIsPasswordOpen((open) => !open)}
            {...bounceTap(bounceStrength)}
            className="flex w-full items-center justify-between rounded-xl py-1 text-sm font-medium text-foreground/80 transition-colors hover:text-foreground"
          >
            {t("profile.edit.changePassword")}
            <ChevronDown
              className={`size-4 text-muted-foreground transition-transform ${isPasswordOpen ? "rotate-180" : ""}`}
            />
          </motion.button>

          <AnimatePresence initial={false}>
            {isPasswordOpen && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.2, ease: "easeOut" }}
                className="overflow-hidden"
              >
                <div className="flex flex-col gap-4 pt-3">
                  <div className="flex flex-col gap-1">
                    <label htmlFor="edit-current-password" className="text-sm font-medium text-foreground/80">
                      {t("profile.edit.currentPasswordLabel")}
                    </label>
                    <div className="relative">
                      <input
                        id="edit-current-password"
                        type={showCurrentPassword ? "text" : "password"}
                        value={currentPassword}
                        onChange={(event) => setCurrentPassword(event.target.value)}
                        autoComplete="current-password"
                        placeholder={t("profile.edit.currentPasswordPlaceholder")}
                        className="w-full rounded-xl border border-border bg-input/60 px-3 py-2 pr-10 text-sm text-foreground outline-none focus:border-primary"
                      />
                      <motion.button
                        type="button"
                        onClick={() => setShowCurrentPassword((value) => !value)}
                        tabIndex={-1}
                        {...bounceTap(bounceStrength, 0.12)}
                        className="absolute inset-y-0 right-0 flex items-center px-3 text-foreground/50 hover:text-foreground"
                      >
                        {showCurrentPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                      </motion.button>
                    </div>
                  </div>

                  <div className="flex flex-col gap-1">
                    <label
                      htmlFor="edit-new-password"
                      className="flex items-center gap-1.5 text-sm font-medium text-foreground/80"
                    >
                      {t("profile.edit.newPasswordLabel")}
                      <FieldHint text={t("auth.passwordHint")} />
                    </label>
                    <div className="relative">
                      <input
                        id="edit-new-password"
                        type={showNewPassword ? "text" : "password"}
                        value={newPassword}
                        onChange={(event) => setNewPassword(event.target.value)}
                        autoComplete="new-password"
                        placeholder={t("profile.edit.newPasswordPlaceholder")}
                        className="w-full rounded-xl border border-border bg-input/60 px-3 py-2 pr-10 text-sm text-foreground outline-none focus:border-primary"
                      />
                      <motion.button
                        type="button"
                        onClick={() => setShowNewPassword((value) => !value)}
                        tabIndex={-1}
                        {...bounceTap(bounceStrength, 0.12)}
                        className="absolute inset-y-0 right-0 flex items-center px-3 text-foreground/50 hover:text-foreground"
                      >
                        {showNewPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                      </motion.button>
                    </div>
                  </div>

                  <div className="flex flex-col gap-1">
                    <label htmlFor="edit-confirm-password" className="text-sm font-medium text-foreground/80">
                      {t("auth.confirmPassword")}
                    </label>
                    <div className="relative">
                      <input
                        id="edit-confirm-password"
                        type={showConfirmPassword ? "text" : "password"}
                        value={confirmPassword}
                        onChange={(event) => setConfirmPassword(event.target.value)}
                        autoComplete="new-password"
                        placeholder={t("auth.confirmPasswordPlaceholder")}
                        className="w-full rounded-xl border border-border bg-input/60 px-3 py-2 pr-10 text-sm text-foreground outline-none focus:border-primary"
                      />
                      <motion.button
                        type="button"
                        onClick={() => setShowConfirmPassword((value) => !value)}
                        tabIndex={-1}
                        {...bounceTap(bounceStrength, 0.12)}
                        className="absolute inset-y-0 right-0 flex items-center px-3 text-foreground/50 hover:text-foreground"
                      >
                        {showConfirmPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                      </motion.button>
                    </div>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        <div className="flex gap-2">
          <button
            type="button"
            onClick={close}
            className="flex-1 rounded-full border border-border px-4 py-2 text-sm font-medium text-foreground/80 transition-colors hover:bg-white/5"
          >
            {t("profile.edit.cancel")}
          </button>
          <motion.button
            type="submit"
            disabled={isSubmitting}
            {...bounceTap(bounceStrength)}
            className="flex-1 rounded-full bg-accent px-4 py-2 text-sm font-medium text-primary transition-colors hover:bg-primary/20 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isSubmitting ? t("profile.edit.saving") : t("profile.edit.save")}
          </motion.button>
        </div>
      </form>
    </>
  );
}
