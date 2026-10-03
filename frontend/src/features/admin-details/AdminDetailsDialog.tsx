import { History, MonitorSmartphone, ShieldCheck, User, UserMinus } from "lucide-react";
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
import { DialogHeader } from "@shared/ui/DialogHeader";
import { Badge } from "@shared/ui/Badge";
import { Card } from "@shared/ui/Card";

export type AdminDetailsFollowUp = "demote";

export type AdminDetailsTab = "profile" | "permissions" | "sessions" | "events";

interface AdminDetailsDialogProps {
  admin: Admin;
  initialTab?: AdminDetailsTab;
  canViewSessions: boolean;
  canViewEvents: boolean;
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
  onUpdated: () => void;
  onFollowUp: (followUp: AdminDetailsFollowUp) => void;
}

function AdminDetailsDialogBody({
  admin: initialAdmin,
  initialTab,
  canViewSessions,
  canViewEvents,
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
        badges={
          <Badge tone={ROLE_BADGE_TONE[admin.role]}>
            {t(`roles.${admin.role}`)}
          </Badge>
        }
        subtitle={admin.login && <span className="font-mono">{admin.login}</span>}
      />

      {tabs.length > 1 && (
        <div className="px-4 pb-3 pt-4">
          <DialogTabs items={tabs} activeKey={tab} onSelect={setTab} />
        </div>
      )}

      <div className={`min-h-0 flex-1 overflow-y-auto px-4 pb-4 ${tabs.length > 1 ? "" : "pt-4"}`}>
        <motion.div
          animate={{ height: contentHeight }}
          transition={{ duration: 0.2, ease: "easeOut" }}
          className="overflow-hidden"
        >
          <div ref={contentRef}>
            {tab === "profile" && <ProfileTab user={admin} />}
            {tab === "permissions" && (
              <Card variant="form">
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
              </Card>
            )}
            {tab === "sessions" && <SessionsTab userId={admin.id} />}
            {tab === "events" && <EventsTab actorId={admin.id} />}
          </div>
        </motion.div>
      </div>

      {isAdmin && (
        <div className="flex items-center gap-2 border-t border-white/[0.07] px-5 py-4">
          <Button
            variant="danger"
            type="button"
            onClick={() => closeWith("demote")}
          >
            <UserMinus className="size-3.5" />
            {t("admins.demote.button")}
          </Button>
          {tab === "permissions" && (
            <div className="ml-auto flex gap-2">
              <Button variant="outline" type="button" onClick={() => setPermissionsRevision((value) => value + 1)}>
                {t("admins.permissionsForm.reset")}
              </Button>
              <Button variant="accent" type="submit" form={ADMIN_PERMISSIONS_FORM_ID} disabled={isSavingPermissions}>
                {t("admins.permissionsForm.submit")}
              </Button>
            </div>
          )}
        </div>
      )}
    </>
  );
}
