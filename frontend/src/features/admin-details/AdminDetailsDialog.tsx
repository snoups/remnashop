import {
  AtSign,
  Ban,
  CalendarDays,
  Coins,
  Gift,
  Hash,
  Languages,
  Mail,
  MonitorSmartphone,
  Percent,
  Send,
  ShieldCheck,
  Ticket,
  User,
  UserMinus,
  X,
} from "lucide-react";
import { motion } from "motion/react";
import { useRef, useState, type ComponentType } from "react";
import { useTranslation } from "react-i18next";

import type { Admin } from "@entities/admin/api";
import { ROLE_BADGE_CLASSNAME, getAdminInitials } from "@entities/admin/display";
import { AdminPermissionsEditor } from "@features/admin-update-permissions/AdminPermissionsEditor";
import { SessionList } from "@entities/auth/SessionList";
import type { Session } from "@entities/auth/sessions";
import { listUserSessions, revokeUserSession } from "@entities/auth/sessions";
import { getErrorMessage } from "@shared/api/http";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { useMeasuredHeight } from "@shared/lib/use-measured-height";
import { BounceIcon } from "@shared/ui/BounceIcon";
import { InfoRow } from "@shared/ui/InfoRow";
import { Modal, useModalClose } from "@shared/ui/Modal";
import { Spinner } from "@shared/ui/Spinner";

export type AdminDetailsFollowUp = "demote";

export type AdminDetailsTab = "profile" | "permissions" | "sessions";

interface AdminDetailsDialogProps {
  admin: Admin;
  initialTab?: AdminDetailsTab;
  canViewSessions: boolean;
  /** The admin was changed from inside the dialog (permissions saved). */
  onUpdated: () => void;
  /** Fires after the exit animation; `followUp` is the action picked in the footer, if any. */
  onClose: (followUp?: AdminDetailsFollowUp) => void;
}

const sectionClassName = "rounded-2xl border border-white/[0.08] bg-white/[0.03] p-1.5";
const sectionTitleClassName =
  "px-2.5 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-wide text-foreground";

export function AdminDetailsDialog({
  admin,
  initialTab = "profile",
  canViewSessions,
  onUpdated,
  onClose,
}: AdminDetailsDialogProps) {
  // the footer action opens its own modal only once this one has animated out
  const followUpRef = useRef<AdminDetailsFollowUp | undefined>(undefined);

  return (
    <Modal onClose={() => onClose(followUpRef.current)} size="lg" scrollable>
      <AdminDetailsDialogBody
        admin={admin}
        initialTab={initialTab}
        canViewSessions={canViewSessions}
        onUpdated={onUpdated}
        onFollowUp={(followUp) => {
          followUpRef.current = followUp;
        }}
      />
    </Modal>
  );
}

interface AdminDetailsDialogBodyProps {
  admin: Admin;
  initialTab: AdminDetailsTab;
  canViewSessions: boolean;
  onUpdated: () => void;
  onFollowUp: (followUp: AdminDetailsFollowUp) => void;
}

function AdminDetailsDialogBody({
  admin: initialAdmin,
  initialTab,
  canViewSessions,
  onUpdated,
  onFollowUp,
}: AdminDetailsDialogBodyProps) {
  const [admin, setAdmin] = useState(initialAdmin);
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const close = useModalClose();
  const [tab, setTab] = useState<AdminDetailsTab>(initialTab);
  const [contentRef, contentHeight] = useMeasuredHeight();
  const isAdmin = admin.role === "ADMIN";

  const tabs: { key: AdminDetailsTab; label: string; icon: ComponentType<{ className?: string }> }[] = [
    { key: "profile", label: t("admins.details.tabs.profile"), icon: User },
    ...(isAdmin
      ? [{ key: "permissions" as const, label: t("admins.details.tabs.permissions"), icon: ShieldCheck }]
      : []),
    ...(canViewSessions
      ? [{ key: "sessions" as const, label: t("admins.details.tabs.sessions"), icon: MonitorSmartphone }]
      : []),
  ];

  const closeWith = (followUp: AdminDetailsFollowUp) => {
    onFollowUp(followUp);
    close();
  };

  return (
    <>
      <div className="flex items-center justify-between gap-3 border-b border-border px-5 py-4">
        <div className="flex min-w-0 items-center gap-2.5">
          <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] text-[11px] font-bold text-foreground backdrop-blur-md">
            {getAdminInitials(admin)}
          </div>
          <div className="min-w-0">
            <div className="flex min-w-0 items-center gap-2">
              <h2 className="truncate text-base font-bold text-foreground">{admin.name}</h2>
              <span
                className={`shrink-0 rounded-full border px-2 py-0.5 text-[10.5px] font-semibold uppercase tracking-wide ${ROLE_BADGE_CLASSNAME[admin.role]}`}
              >
                {t(`roles.${admin.role}`)}
              </span>
            </div>
            {admin.login && <p className="mt-0.5 truncate font-mono text-[12px] text-muted-foreground">{admin.login}</p>}
          </div>
        </div>
        <button
          type="button"
          onClick={close}
          aria-label={t("profile.edit.close")}
          className="flex size-8 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-white/[0.06] hover:text-foreground"
        >
          <X className="size-4" />
        </button>
      </div>

      {tabs.length > 1 && (
        <div className="px-4 pb-3 pt-4">
          <div
            role="tablist"
            className="flex gap-1 rounded-full border border-glass-border bg-white/[0.03] p-1 backdrop-blur-md"
          >
            {tabs.map((item) => {
              const isActive = tab === item.key;
              return (
                <motion.button
                  key={item.key}
                  type="button"
                  role="tab"
                  aria-selected={isActive}
                  onClick={() => setTab(item.key)}
                  className="group relative isolate block min-w-0 flex-1 rounded-full text-sm font-medium"
                  initial="rest"
                  whileHover="hover"
                  whileTap="tap"
                >
                  <motion.span
                    aria-hidden
                    variants={{ rest: { scale: 1 }, tap: { scale: 1 + 0.05 * bounceStrength } }}
                    className={`absolute inset-0 rounded-full transition-colors ${
                      isActive ? "bg-accent" : "group-hover:bg-white/[0.06]"
                    }`}
                  />
                  <span
                    className={`relative z-10 flex items-center justify-center gap-1.5 whitespace-nowrap px-3 py-1.5 text-[13px] ${
                      isActive ? "text-primary" : "text-foreground"
                    }`}
                  >
                    <BounceIcon icon={item.icon} size={14} hoverSize={17} />
                    {item.label}
                  </span>
                </motion.button>
              );
            })}
          </div>
        </div>
      )}

      <div className={`min-h-0 flex-1 overflow-y-auto px-4 pb-4 ${tabs.length > 1 ? "" : "pt-4"}`}>
        <motion.div
          animate={{ height: contentHeight }}
          transition={{ duration: 0.2, ease: "easeOut" }}
          className="overflow-hidden"
        >
          <div ref={contentRef}>
            {tab === "profile" && <ProfileTab admin={admin} />}
            {tab === "permissions" && (
              <PermissionsTab
                admin={admin}
                onSaved={(updated) => {
                  setAdmin(updated);
                  onUpdated();
                }}
              />
            )}
            {tab === "sessions" && <SessionsTab userId={admin.id} />}
          </div>
        </motion.div>
      </div>

      <div className="flex items-center justify-between gap-2 border-t border-white/[0.07] px-5 py-4">
        {isAdmin ? (
          <motion.button
            type="button"
            onClick={() => closeWith("demote")}
            {...bounceTap(bounceStrength)}
            className="flex items-center gap-2 rounded-full px-3 py-2 text-sm font-medium text-error transition-colors hover:bg-error/10"
          >
            <UserMinus className="size-4" />
            {t("admins.demote.button")}
          </motion.button>
        ) : (
          <span />
        )}
        <div className="flex gap-2">
          <button
            type="button"
            onClick={close}
            className="rounded-full border border-border px-4 py-2 text-sm font-medium text-foreground/80 transition-colors hover:bg-white/5"
          >
            {t("admins.details.close")}
          </button>
        </div>
      </div>
    </>
  );
}

function ProfileTab({ admin }: { admin: Admin }) {
  const { t } = useTranslation();
  const dash = "—";
  const yesNo = (value: boolean) => (value ? t("users.details.yes") : t("users.details.no"));
  const blocked = yesNo(admin.is_blocked);
  const trialAvailable = yesNo(admin.is_trial_available);
  const createdAt = admin.created_at ? new Date(admin.created_at).toLocaleString() : undefined;

  return (
    <div className="flex flex-col gap-3">
      <section className={sectionClassName}>
        <h3 className={sectionTitleClassName}>{t("admins.details.sections.account")}</h3>
        <InfoRow icon={Hash} label={t("users.details.id")} copyValue={String(admin.id)}>
          {admin.id}
        </InfoRow>
        <InfoRow
          icon={AtSign}
          label={t("users.details.username")}
          copyValue={admin.username ? `@${admin.username}` : undefined}
        >
          {admin.username ? `@${admin.username}` : dash}
        </InfoRow>
        <InfoRow
          icon={Send}
          label={t("users.details.telegramId")}
          copyValue={admin.telegram_id !== null ? String(admin.telegram_id) : undefined}
        >
          {admin.telegram_id ?? dash}
        </InfoRow>
        <InfoRow icon={Mail} label={t("users.details.email")} copyValue={admin.email ?? undefined}>
          {admin.email ?? dash}
        </InfoRow>
        <InfoRow icon={Languages} label={t("users.details.language")} copyValue={admin.language.toUpperCase()}>
          {admin.language.toUpperCase()}
        </InfoRow>
        <InfoRow icon={Ban} label={t("admins.details.blocked")} copyValue={blocked}>
          <span className={admin.is_blocked ? "text-error" : undefined}>{blocked}</span>
        </InfoRow>
        <InfoRow icon={CalendarDays} label={t("users.details.createdAt")} copyValue={createdAt}>
          {createdAt ?? dash}
        </InfoRow>
      </section>

      <section className={sectionClassName}>
        <h3 className={sectionTitleClassName}>{t("admins.details.sections.purchases")}</h3>
        <InfoRow icon={Coins} label={t("users.details.points")} copyValue={String(admin.points)}>
          {admin.points}
        </InfoRow>
        <InfoRow icon={Percent} label={t("users.details.personalDiscount")} copyValue={`${admin.personal_discount}%`}>
          {admin.personal_discount}%
        </InfoRow>
        <InfoRow icon={Ticket} label={t("users.details.purchaseDiscount")} copyValue={`${admin.purchase_discount}%`}>
          {admin.purchase_discount}%
        </InfoRow>
        <InfoRow icon={Gift} label={t("users.details.trialAvailable")} copyValue={trialAvailable}>
          {trialAvailable}
        </InfoRow>
      </section>
    </div>
  );
}

function PermissionsTab({ admin, onSaved }: { admin: Admin; onSaved: (admin: Admin) => void }) {
  // bumping the key remounts the editor: cancel drops unsaved toggles, save re-seeds from the response
  const [revision, setRevision] = useState(0);

  return (
    <AdminPermissionsEditor
      key={revision}
      admin={admin}
      onSaved={(updated) => {
        onSaved(updated);
        setRevision((value) => value + 1);
      }}
      onCancel={() => setRevision((value) => value + 1)}
      className="rounded-2xl border border-white/[0.08] bg-white/[0.03] px-4 pb-4 pt-1.5"
    />
  );
}

function SessionsTab({ userId }: { userId: number }) {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const [state, reload] = useAsyncResource((signal) => listUserSessions(userId, signal));
  const [pendingRevoke, setPendingRevoke] = useState<Session | null>(null);

  const handleRevoke = async (sessionId: number) => {
    try {
      await revokeUserSession(userId, sessionId);
      reload();
    } catch (err) {
      toast.error(getErrorMessage(err, t("sessions.revokeError")));
    }
  };

  if (pendingRevoke) {
    return (
      <div className="flex flex-col gap-4 rounded-2xl border border-white/[0.08] bg-white/[0.03] p-4">
        <div>
          <p className="text-sm font-bold text-foreground">{t("sessions.revokeTitle")}</p>
          <p className="mt-1 text-[12.5px] text-muted-foreground">{t("sessions.revokeConfirm")}</p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setPendingRevoke(null)}
            className="flex-1 rounded-full border border-border px-4 py-2 text-sm font-medium text-foreground/80 transition-colors hover:bg-white/5"
          >
            {t("sessions.cancel")}
          </button>
          <motion.button
            type="button"
            onClick={() => {
              void handleRevoke(pendingRevoke.id);
              setPendingRevoke(null);
            }}
            {...bounceTap(bounceStrength)}
            className="flex-1 rounded-full border border-error/30 bg-error/10 px-4 py-2 text-sm font-medium text-error transition-colors hover:bg-error/20"
          >
            {t("sessions.revoke")}
          </motion.button>
        </div>
      </div>
    );
  }

  return (
    <div className={sectionClassName}>
      {state.kind === "loading" && <Spinner className="py-8" />}
      {state.kind === "error" && <p className="p-3 text-sm text-error">{t("sessions.loadError")}</p>}
      {state.kind === "ready" && <SessionList sessions={state.data} onRequestRevoke={setPendingRevoke} />}
    </div>
  );
}
