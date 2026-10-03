import { ExternalLink } from "lucide-react";
import { useTranslation } from "react-i18next";

import { localized } from "@entities/announcements/api";
import type { Announcement } from "@entities/announcements/api";
import { AnnouncementIcon } from "@entities/announcements/AnnouncementIcon";
import { formatRelative } from "@shared/lib/relative-time";
import { Button } from "@shared/ui/Button";
import { DialogHeader } from "@shared/ui/DialogHeader";
import { Modal } from "@shared/ui/Modal";

interface AnnouncementDialogProps {
  announcement: Announcement;
  onClose: () => void;
}

export function AnnouncementDialog({ announcement, onClose }: AnnouncementDialogProps) {
  const { t, i18n } = useTranslation();
  const critical = announcement.severity === "critical";
  const text = localized(announcement.text, i18n.language);
  const { url } = announcement;

  return (
    <Modal onClose={onClose} size="md" scrollable>
      <DialogHeader
        glyph={<AnnouncementIcon icon={announcement.icon} className="size-4" />}
        tone={critical ? "danger" : "primary"}
        title={localized(announcement.title, i18n.language)}
        subtitle={
          <>
            {critical && `${t("announcements.critical")} · `}
            {formatRelative(announcement.notify_at, i18n.language)}
          </>
        }
      />

      {text && (
        <div className="scroll-fade-y min-h-0 flex-1 overflow-y-auto px-5 py-4">
          <p className="whitespace-pre-line text-[13.5px] leading-relaxed text-foreground/90">{text}</p>
        </div>
      )}

      {url && (
        <div className="flex shrink-0 justify-end border-t border-border px-5 py-4">
          <Button variant="accent" onClick={() => window.open(url, "_blank", "noopener,noreferrer")}>
            {localized(announcement.url_label, i18n.language) || t("announcements.openLink")}
            <ExternalLink className="size-4" />
          </Button>
        </div>
      )}
    </Modal>
  );
}
