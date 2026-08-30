import { X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useTranslation } from "react-i18next";

import type { UserListItem } from "@entities/user/api";
import type { Role } from "@shared/types/rbac";
import { DialogPortal } from "@shared/ui/DialogPortal";

const ROLE_BADGE_CLASSNAME: Record<Role, string> = {
  USER: "border-border bg-white/[0.04] text-muted-foreground",
  ADMIN: "border-border bg-white/[0.06] text-foreground/80",
  OWNER: "border-primary/40 bg-accent text-primary",
  SYSTEM: "border-warning/30 bg-warning/10 text-warning",
};

interface UserDetailsDialogProps {
  user: UserListItem;
  onClose: () => void;
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 py-2">
      <span className="text-[12.5px] text-muted-foreground">{label}</span>
      <span className="truncate text-[13px] font-medium text-foreground">{value}</span>
    </div>
  );
}

function getInitials(user: UserListItem): string {
  return (user.login ?? user.name).slice(0, 2).toUpperCase();
}

export function UserDetailsDialog({ user, onClose }: UserDetailsDialogProps) {
  const { t } = useTranslation();

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
            onClick={onClose}
          />

          <motion.div
            initial={{ opacity: 0, scale: 0.94, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.94, y: 8 }}
            transition={{ duration: 0.18, ease: "easeOut" }}
            className="relative z-50 w-full max-w-sm rounded-dialog border border-white/[0.14] bg-popover/60 shadow-[0_24px_48px_-20px_rgba(4,8,20,0.6),inset_0_1px_0_rgba(232,236,251,0.16)] backdrop-blur-2xl backdrop-saturate-150"
          >
            <div className="flex items-center justify-between border-b border-border px-5 py-4">
              <div className="flex min-w-0 items-center gap-3">
                <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-white/[0.06] text-[12.5px] font-bold text-foreground">
                  {getInitials(user)}
                </div>
                <div className="min-w-0">
                  <h2 className="truncate text-base font-bold text-foreground">{user.name}</h2>
                  <span
                    className={`inline-block rounded-full border px-2 py-0.5 text-[10.5px] font-semibold uppercase tracking-wide ${ROLE_BADGE_CLASSNAME[user.role]}`}
                  >
                    {t(`roles.${user.role}`)}
                  </span>
                </div>
              </div>
              <button
                type="button"
                onClick={onClose}
                aria-label={t("profile.edit.close")}
                className="flex size-8 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-white/[0.06] hover:text-foreground"
              >
                <X className="size-4" />
              </button>
            </div>

            <div className="divide-y divide-border/50 px-5 pb-4 pt-1">
              <DetailRow label={t("users.details.id")} value={String(user.id)} />
              <DetailRow label={t("users.details.login")} value={user.login ?? "—"} />
              <DetailRow label={t("users.details.username")} value={user.username ? `@${user.username}` : "—"} />
              <DetailRow label={t("users.details.telegramId")} value={user.telegram_id !== null ? String(user.telegram_id) : "—"} />
              <DetailRow label={t("users.details.email")} value={user.email ?? "—"} />
              <DetailRow label={t("users.details.language")} value={user.language.toUpperCase()} />
              <DetailRow
                label={t("users.details.status")}
                value={user.is_blocked ? t("users.blocked") : t("users.details.active")}
              />
              <DetailRow
                label={t("users.details.createdAt")}
                value={user.created_at ? new Date(user.created_at).toLocaleString() : "—"}
              />
            </div>
          </motion.div>
        </motion.div>
      </AnimatePresence>
    </DialogPortal>
  );
}
