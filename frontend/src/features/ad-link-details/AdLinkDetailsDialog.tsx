import { BarChart3, Link2, Pause, Pencil, Play, StickyNote, Trash2, Users } from "lucide-react";
import { motion } from "motion/react";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { type AdLink, updateAdLink } from "@entities/advertising/api";
import { AdLinkEditForm } from "@features/ad-link-edit/AdLinkEditForm";
import { AD_LINK_EDIT_FORM_ID, useAdLinkEditForm } from "@features/ad-link-edit/use-ad-link-edit-form";
import { AdLinkShareMenu } from "@features/ad-link-share/AdLinkShareMenu";
import { AdLinkStatsPanel } from "@features/ad-link-stats/AdLinkStatsPanel";
import { AdLinkUsersList } from "@features/ad-link-stats/AdLinkUsersList";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { useMeasuredHeight } from "@shared/lib/use-measured-height";
import { DialogTabs, type DialogTabItem } from "@shared/ui/DialogTabs";
import { Modal } from "@shared/ui/Modal";
import { useModalClose } from "@shared/ui/modal-hooks";
import { Button } from "@shared/ui/Button";
import { DialogHeader } from "@shared/ui/DialogHeader";
import { Badge } from "@shared/ui/Badge";
import { Card } from "@shared/ui/Card";

export type AdLinkDetailsFollowUp = "delete";

type AdLinkDetailsTab = "overview" | "users" | "settings";


interface AdLinkDetailsDialogProps {
  adLink: AdLink;
  periodDays: number;
  createdFrom?: string;
  canViewStats: boolean;
  canViewUsers: boolean;
  canShare: boolean;
  canUpdate: boolean;
  canDelete: boolean;
  onSaved: (adLink: AdLink) => void;
  /** Fires after the exit animation; `followUp` is the action picked in the footer, if any. */
  onClose: (followUp?: AdLinkDetailsFollowUp) => void;
}

export function AdLinkDetailsDialog({ onClose, ...props }: AdLinkDetailsDialogProps) {
  // the delete confirmation opens only once this modal has animated out
  const followUpRef = useRef<AdLinkDetailsFollowUp | undefined>(undefined);

  return (
    <Modal onClose={() => onClose(followUpRef.current)} size="lg" scrollable>
      <AdLinkDetailsDialogBody
        {...props}
        onFollowUp={(followUp) => {
          followUpRef.current = followUp;
        }}
      />
    </Modal>
  );
}

function AdLinkDetailsDialogBody({
  adLink,
  periodDays,
  createdFrom,
  canViewStats,
  canViewUsers,
  canShare,
  canUpdate,
  canDelete,
  onSaved,
  onFollowUp,
}: Omit<AdLinkDetailsDialogProps, "onClose"> & { onFollowUp: (followUp: AdLinkDetailsFollowUp) => void }) {
  const { t } = useTranslation();
  const close = useModalClose();
  const [tab, setTab] = useState<AdLinkDetailsTab>("overview");
  const [contentRef, contentHeight] = useMeasuredHeight();
  const [isToggling, setIsToggling] = useState(false);
  const editForm = useAdLinkEditForm(adLink, onSaved);

  const tabs: DialogTabItem<AdLinkDetailsTab>[] = [
    { key: "overview", label: t("advertising.details.tabs.overview"), icon: BarChart3 },
    ...(canViewUsers ? [{ key: "users" as const, label: t("advertising.details.tabs.users"), icon: Users }] : []),
    ...(canUpdate ? [{ key: "settings" as const, label: t("advertising.details.tabs.settings"), icon: Pencil }] : []),
  ];

  const handleToggleActive = async () => {
    setIsToggling(true);
    try {
      onSaved(await updateAdLink(adLink.id, { is_active: !adLink.is_active }));
    } catch (err) {
      toast.error(getErrorMessage(err, t("advertising.edit.error")));
    } finally {
      setIsToggling(false);
    }
  };

  const deleteButton = canDelete && (
    <Button
      variant="danger"
      type="button"
      onClick={() => {
        onFollowUp("delete");
        close();
      }}
    >
      <Trash2 className="size-3.5" />
      {t("advertising.delete.button")}
    </Button>
  );

  return (
    <>
      <DialogHeader
        icon={Link2}
        title={adLink.name}
        badges={
          <Badge tone={adLink.is_active ? "success" : "neutral"}>
            {adLink.is_active ? t("advertising.status.active") : t("advertising.status.paused")}
          </Badge>
        }
        subtitle={<span className="font-mono">{adLink.code}</span>}
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
            {tab === "overview" && (
              <div className="flex flex-col gap-3">
                {adLink.note && (
                  <Card variant="list" title={t("advertising.edit.noteLabel")} icon={StickyNote}>
                    <p className="whitespace-pre-wrap break-words px-2.5 pb-1.5 text-[13px] text-foreground">
                      {adLink.note}
                    </p>
                  </Card>
                )}

                {canViewStats && (
                  <AdLinkStatsPanel
                    key={`${adLink.id}-${periodDays}`}
                    adLink={adLink}
                    periodDays={periodDays}
                    createdFrom={createdFrom}
                  />
                )}
              </div>
            )}
            {tab === "users" && <AdLinkUsersList adLink={adLink} />}
            {tab === "settings" && <AdLinkEditForm form={editForm} />}
          </div>
        </motion.div>
      </div>

      {tab === "settings" ? (
        <div className="flex items-center justify-between gap-2 border-t border-white/[0.07] px-5 py-4">
          <div className="flex gap-2">
            {deleteButton}
            <Button variant="outline" onClick={() => void handleToggleActive()} disabled={isToggling}>
              {adLink.is_active ? <Pause className="size-3.5" /> : <Play className="size-3.5" />}
              {adLink.is_active ? t("advertising.pause") : t("advertising.resume")}
            </Button>
          </div>
          <Button variant="accent" type="submit" form={AD_LINK_EDIT_FORM_ID} disabled={!editForm.canSubmit}>
            {editForm.isSubmitting ? t("advertising.edit.saving") : t("advertising.edit.save")}
          </Button>
        </div>
      ) : (
        canShare && (
          <div className="flex justify-end border-t border-white/[0.07] px-5 py-4">
            <AdLinkShareMenu key={`${adLink.id}-${adLink.allow_bot}-${adLink.allow_webcabinet}`} adLink={adLink} />
          </div>
        )
      )}
    </>
  );
}
