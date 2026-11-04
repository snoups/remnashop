import { History, MonitorSmartphone, ShieldCheck, Trash2, User, UserMinus } from "lucide-react";
import { motion } from "motion/react";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import type { Admin } from "@entities/admin/api";
import { ROLE_BADGE_TONE } from "@entities/admin/display";
import {
  ADMIN_PERMISSIONS_FORM_ID,
  AdminPermissionsEditor,
} from "@features/admin-update-permissions/AdminPermissionsEditor";
import { EventsTab, ProfileTab, SessionsTab } from "@features/user-details/UserDetailsTabs";
import { useMeasuredHeight } from "@shared/lib/use-measured-height";
import { initials } from "@shared/lib/initials";
import { DialogTabs, type DialogTabItem } from "@shared/ui/DialogTabs";
import { Modal } from "@shared/ui/Modal";
import { useModalClose } from "@shared/ui/modal-hooks";
import { Button } from "@shared/ui/Button";
import { GLASS_DIALOG_CARD_CLASS } from "@shared/ui/classes";
import { DialogHeader } from "@shared/ui/glass/DialogHeader";
import { Badge } from "@shared/ui/Badge";

export type AdminDetailsFollowUp = "demote" | "delete";

export type AdminDetailsTab = "profile" | "permissions" | "sessions" | "events";

interface AdminDetailsDialogProps {
  admin: Admin;
  initialTab?: AdminDetailsTab;
  canViewSessions: boolean;
  canViewEvents: boolean;
  canDelete: boolean;
  /** The admin was changed from inside the dialog (permissions saved). */
  onUpdated: () => void;
  /** Fires after the exit animation; `followUp` is the action picked in the footer, if any. */
  onClose: (followUp?: AdminDetailsFollowUp) => void;
}

export function AdminDetailsDialog({
  admin,
  initialTab = "profile",
  canViewSessions,
  canViewEvents,
  canDelete,
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
        canViewEvents={canViewEvents}
        canDelete={canDelete}
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
  canViewEvents: boolean;
  canDelete: boolean;
  onUpdated: () => void;
  onFollowUp: (followUp: AdminDetailsFollowUp) => void;
}

function AdminDetailsDialogBody({
  admin: initialAdmin,
  initialTab,
  canViewSessions,
  canViewEvents,
  canDelete,
  onUpdated,
  onFollowUp,
}: AdminDetailsDialogBodyProps) {
  const [admin, setAdmin] = useState(initialAdmin);
  const { t } = useTranslation();
  const close = useModalClose();
  const [tab, setTab] = useState<AdminDetailsTab>(initialTab);
  const [contentRef, contentHeight] = useMeasuredHeight();
  // bumping it remounts the permissions editor: reset drops unsaved toggles, save re-seeds from the response
  const [permissionsRevision, setPermissionsRevision] = useState(0);
  const [isSavingPermissions, setIsSavingPermissions] = useState(false);
  const isAdmin = admin.role === "ADMIN";

  const tabs: DialogTabItem<AdminDetailsTab>[] = [
    { key: "profile", label: t("admins.details.tabs.profile"), icon: User },
    ...(isAdmin
      ? [{ key: "permissions" as const, label: t("admins.details.tabs.permissions"), icon: ShieldCheck }]
      : []),
    ...(canViewSessions
      ? [{ key: "sessions" as const, label: t("admins.details.tabs.sessions"), icon: MonitorSmartphone }]
      : []),
    ...(canViewEvents ? [{ key: "events" as const, label: t("admins.details.tabs.events"), icon: History }] : []),
  ];

  const closeWith = (followUp: AdminDetailsFollowUp) => {
    onFollowUp(followUp);
    close();
  };

  return (
    <>
      <DialogHeader
        glyph={<span className="text-[11px] font-bold">{initials(admin.login ?? admin.name)}</span>}
        title={admin.name}
        subtitle={admin.login && <span className="font-mono">{admin.login}</span>}
        actions={<Badge borderless tone={ROLE_BADGE_TONE[admin.role]}>{t(`roles.${admin.role}`)}</Badge>}
      />

      {tabs.length > 1 && (
        <div className="px-3 pt-3">
          <DialogTabs items={tabs} activeKey={tab} onSelect={setTab} />
        </div>
      )}

      <div className="scroll-fade-y min-h-0 flex-1 overflow-y-auto p-3 [--dialog-pad:0.75rem]">
        <motion.div
          animate={{ height: contentHeight }}
          transition={{ duration: 0.2, ease: "easeOut" }}
          className="overflow-hidden"
        >
          <div ref={contentRef}>
            {tab === "profile" && <ProfileTab user={admin} />}
            {tab === "permissions" && (
              <div className={GLASS_DIALOG_CARD_CLASS}>
                <AdminPermissionsEditor
                  key={permissionsRevision}
                  admin={admin}
                  onSaved={(updated) => {
                    setAdmin(updated);
                    setPermissionsRevision((value) => value + 1);
                    onUpdated();
                  }}
                  onSubmittingChange={setIsSavingPermissions}
                />
              </div>
            )}
            {tab === "sessions" && <SessionsTab userId={admin.id} />}
            {tab === "events" && <EventsTab userId={admin.id} by="actor" />}
          </div>
        </motion.div>
      </div>

      {isAdmin && (
        <div className="flex items-center gap-2 border-t border-white/[0.08] p-4">
          <Button
            variant="glassDanger"
            type="button"
            icon={UserMinus}
            onClick={() => closeWith("demote")}
          >
            {t("admins.demote.button")}
          </Button>
          {canDelete && (
            <Button variant="glassDanger" type="button" icon={Trash2} onClick={() => closeWith("delete")}>
              {t("common.delete")}
            </Button>
          )}
          {tab === "permissions" && (
            <div className="ml-auto flex gap-2">
              <Button variant="glass" type="button" onClick={() => setPermissionsRevision((value) => value + 1)}>
                {t("common.reset")}
              </Button>
              <Button variant="glassAccent" type="submit" form={ADMIN_PERMISSIONS_FORM_ID} isLoading={isSavingPermissions}>
                {t("common.save")}
              </Button>
            </div>
          )}
        </div>
      )}
    </>
  );
}
