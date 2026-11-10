import type { ParseKeys } from "i18next";
import {
  Activity,
  AtSign,
  Braces,
  Check,
  Clock,
  Copy,
  Crosshair,
  Globe,
  Hash,
  Info,
  KeyRound,
  Mail,
  MousePointerClick,
  Send,
  Shield,
  Tag,
  User,
} from "lucide-react";
import { motion } from "motion/react";
import { useState, type ComponentType } from "react";
import { useTranslation } from "react-i18next";

import type { EventLogEntry } from "@entities/event-log/api";
import {
  ANONYMOUS_EVENT_TYPES,
  PAYLOAD_TARGET_KEY,
  eventTitle,
  getInitiator,
  getUserSnapshot,
  isApiToken,
  isSystemActor,
} from "@entities/event-log/describe-entry";
import type { UserSnapshot } from "@entities/event-log/describe-entry";
import { EventTypeIcon } from "@entities/event-log/EventTypeIcon";
import { OpenUserFooter } from "@features/open-user/OpenUserFooter";
import { copyToClipboard } from "@shared/lib/clipboard";
import { useMeasuredHeight } from "@shared/lib/use-measured-height";
import { DialogTabs, type DialogTabItem } from "@shared/ui/DialogTabs";
import { InfoRow } from "@shared/ui/InfoRow";
import { Modal } from "@shared/ui/Modal";
import { DialogCard } from "@shared/ui/glass/DialogCard";
import { DialogHeader } from "@shared/ui/glass/DialogHeader";
import { IconButton } from "@shared/ui/IconButton";
import { formatDateTime } from "@shared/lib/relative-time";
import { GLASS_DIALOG_BODY_CLASS, SECTION_TITLE_CLASS } from "@shared/ui/classes";

// a staff address the reader may not see
const MASKED_IP = "***";

interface EventDetailDialogProps {
  entry: EventLogEntry;
  onClose: () => void;
}

type EventDetailTab = "details" | "payload";

interface ParticipantSectionProps {
  title: string;
  icon: ComponentType<{ className?: string }>;
  user: UserSnapshot | undefined;
  missingLabel?: string;
  ipAddress?: string | null;
}

function ParticipantSection({ title, icon: Icon, user, missingLabel, ipAddress }: ParticipantSectionProps) {
  const { t } = useTranslation();
  const name = user ? user.name || t("common.none") : (missingLabel ?? t("common.none"));
  const roleLabel =
    user === undefined
      ? undefined
      : isApiToken(user)
        ? t("eventLog.detail.apiToken")
        : user.role
          ? t(`roles.${user.role}` as ParseKeys)
          : undefined;
  // id 0 and below is a synthetic actor (API token / system), not a real row
  const userId = user?.id && user.id > 0 ? String(user.id) : undefined;
  const telegramId = user?.telegram_id && user.telegram_id > 0 ? String(user.telegram_id) : undefined;

  return (
    <DialogCard title={title} icon={Icon}>
      <InfoRow icon={User} label={t("eventLog.detail.name")} copyValue={user?.name || undefined}>
        <span className="truncate">{name}</span>
      </InfoRow>
      {user?.login && (
        <InfoRow icon={KeyRound} label={t("users.details.login")} copyValue={user.login} mono>
          <span className="truncate">{user.login}</span>
        </InfoRow>
      )}
      {userId && (
        <InfoRow icon={Hash} label={t("users.details.id")} copyValue={userId} mono>
          {userId}
        </InfoRow>
      )}
      {user?.email && (
        <InfoRow icon={Mail} label={t("users.details.email")} copyValue={user.email} mono>
          <span className="truncate">{user.email}</span>
        </InfoRow>
      )}
      {roleLabel && (
        <InfoRow icon={Shield} label={t("eventLog.detail.role")} copyValue={roleLabel}>
          {roleLabel}
        </InfoRow>
      )}
      {ipAddress && (
        <InfoRow
          icon={Globe}
          label={t("eventLog.detail.ip")}
          copyValue={ipAddress === MASKED_IP ? undefined : ipAddress}
          mono
        >
          {ipAddress}
        </InfoRow>
      )}
      {(telegramId || user?.username) && (
        <div className="m-1 rounded-xl border border-white/[0.08] bg-white/[0.02] p-1">
          <h4 className={SECTION_TITLE_CLASS}>
            <Send className="size-3.5" />
            {t("eventLog.detail.telegram")}
          </h4>
          {telegramId && (
            <InfoRow icon={Send} label={t("users.details.telegramId")} copyValue={telegramId} mono>
              {telegramId}
            </InfoRow>
          )}
          {user?.username && (
            <InfoRow icon={AtSign} label={t("users.details.username")} copyValue={`@${user.username}`} mono>
              <span className="truncate">@{user.username}</span>
            </InfoRow>
          )}
        </div>
      )}
    </DialogCard>
  );
}

export function EventDetailDialog({ entry, onClose }: EventDetailDialogProps) {
  return (
    <Modal onClose={onClose} size="lg" scrollable>
      <EventDetailDialogBody entry={entry} />
    </Modal>
  );
}

function EventDetailDialogBody({ entry }: { entry: EventLogEntry }) {
  const { t, i18n } = useTranslation();
  const [tab, setTab] = useState<EventDetailTab>("details");
  const targetUser = getUserSnapshot(entry, PAYLOAD_TARGET_KEY);
  const initiator = getInitiator(entry);
  // background tasks/webhooks: nothing to show beyond "System"
  const isSystemInitiated = initiator
    ? isSystemActor(initiator)
    : !ANONYMOUS_EVENT_TYPES.has(entry.event_type);
  const otherPayload = Object.fromEntries(
    Object.entries(entry.payload ?? {}).filter(([key]) => key !== PAYLOAD_TARGET_KEY),
  );
  const hasOtherPayload = Object.keys(otherPayload).length > 0;
  const [isCopied, setIsCopied] = useState(false);
  const [contentRef, contentHeight] = useMeasuredHeight();

  const tabs: DialogTabItem<EventDetailTab>[] = [
    { key: "details", label: t("eventLog.detail.tabs.details"), icon: Info },
    ...(hasOtherPayload
      ? [{ key: "payload" as const, label: t("eventLog.detail.tabs.payload"), icon: Braces }]
      : []),
  ];

  const handleCopyPayload = () => {
    void copyToClipboard(JSON.stringify(otherPayload, null, 2)).then((copied) => {
      if (!copied) return;
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 1500);
    });
  };

  return (
    <>
      <DialogHeader
        glyph={<EventTypeIcon eventType={entry.event_type} className="size-4" />}
        title={eventTitle(entry, t)}
      />

      {tabs.length > 1 && (
        <div className="px-3 pt-3">
          <DialogTabs items={tabs} activeKey={tab} onSelect={setTab} />
        </div>
      )}

      <div className={GLASS_DIALOG_BODY_CLASS}>
        <motion.div
          animate={{ height: contentHeight }}
          transition={{ duration: 0.2, ease: "easeOut" }}
          className="overflow-hidden"
        >
          <div ref={contentRef}>
            {tab === "details" && (
              <div className="flex flex-col gap-3">
                <DialogCard title={t("eventLog.detail.sections.event")} icon={Activity}>
                  <InfoRow icon={Hash} label={t("eventLog.detail.id")} copyValue={String(entry.id)} mono>
                    {entry.id}
                  </InfoRow>
                  <InfoRow
                    icon={Clock}
                    label={t("eventLog.columns.occurredAt")}
                    copyValue={formatDateTime(entry.occurred_at, i18n.language)}
                    mono
                  >
                    {formatDateTime(entry.occurred_at, i18n.language)}
                  </InfoRow>
                  <InfoRow icon={Tag} label={t("eventLog.detail.eventCode")} copyValue={entry.event_type} mono>
                    {entry.event_type}
                  </InfoRow>
                </DialogCard>

                {!isSystemInitiated && (
                  <ParticipantSection
                    title={t("eventLog.columns.actor")}
                    icon={MousePointerClick}
                    user={initiator}
                    missingLabel={t("eventLog.detail.anonymous")}
                    ipAddress={entry.ip_address}
                  />
                )}
                {targetUser && (
                  <ParticipantSection title={t("eventLog.detail.target")} icon={Crosshair} user={targetUser} />
                )}
              </div>
            )}

            {tab === "payload" && (
              <DialogCard>
                <div className="flex items-center justify-between">
                  <h3 className={SECTION_TITLE_CLASS}>
                    <Braces className="size-3.5" />
                    {t("eventLog.detail.json")}
                  </h3>
                  <IconButton size="7"
                    onClick={handleCopyPayload}
                  >
                    <Copy className="size-3.5" />
                  </IconButton>
                </div>
                <div className="relative mt-1">
                  <pre
                    className={`glass-well overflow-x-auto rounded-md p-2.5 font-mono text-xs text-foreground/80 transition-opacity ${
                      isCopied ? "opacity-20" : ""
                    }`}
                  >
                    {JSON.stringify(otherPayload, null, 2)}
                  </pre>
                  {isCopied && (
                    <span className="absolute inset-0 flex items-center justify-center gap-1.5 text-xs font-medium text-primary">
                      <Check className="size-3.5" />
                      {t("app.copied")}
                    </span>
                  )}
                </div>
              </DialogCard>
            )}
          </div>
        </motion.div>
      </div>

      <OpenUserFooter
        links={[
          {
            label: t("eventLog.detail.openInitiator"),
            icon: MousePointerClick,
            user: isSystemInitiated ? undefined : initiator,
          },
          { label: t("eventLog.detail.openTarget"), icon: Crosshair, user: targetUser },
        ]}
      />
    </>
  );
}

