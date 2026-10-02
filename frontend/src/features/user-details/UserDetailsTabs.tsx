import {
  AtSign,
  Ban,
  CalendarDays,
  Gift,
  Hash,
  KeyRound,
  Languages,
  Link2,
  Mail,
  Megaphone,
  Send,
  Trash2,
  User,
} from "lucide-react";
import { motion } from "motion/react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { SessionList } from "@entities/auth/SessionList";
import type { Session } from "@entities/auth/sessions";
import { listUserSessions, revokeUserSession } from "@entities/auth/sessions";
import { getUserAdAttribution } from "@entities/advertising/api";
import { listEventLog } from "@entities/event-log/api";
import type { EventLogEntry } from "@entities/event-log/api";
import { EventTypeIcon } from "@entities/event-log/EventTypeIcon";
import type { UserListItem } from "@entities/user/api";
import { useCurrentUser } from "@entities/user/use-current-user";
import { EventDetailDialog } from "@features/event-details/EventDetailDialog";
import { getErrorMessage } from "@shared/api/http";
import { bounceTap } from "@shared/lib/bounceState";
import { toast } from "@shared/lib/toast";
import { formatDateTime } from "@shared/lib/relative-time";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { Card } from "@shared/ui/Card";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { EmptyState } from "@shared/ui/EmptyState";
import { InfoRow } from "@shared/ui/InfoRow";
import { KpiTile } from "@shared/ui/KpiTile";
import { LoadMoreButton } from "@shared/ui/LoadMoreButton";
import { Spinner } from "@shared/ui/Spinner";
import { Tag } from "@shared/ui/Tag";

// Profile/sessions/events tabs shared by the user and admin details dialogs.

const EVENTS_PAGE_SIZE = 10;

// "ru" -> "Русский" in the UI language; an unknown code stays as is
function languageName(code: string, uiLanguage: string): string {
  try {
    const name = new Intl.DisplayNames(uiLanguage, { type: "language" }).of(code.toLowerCase()) ?? code;
    return name.charAt(0).toUpperCase() + name.slice(1);
  } catch {
    return code.toUpperCase();
  }
}

const sectionTitleClassName =
  "flex items-center gap-1.5 px-2.5 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-wide text-foreground";

export function ProfileTab({ user }: { user: UserListItem }) {
  const { t, i18n } = useTranslation();
  const currentUserState = useCurrentUser();
  const dash = "—";
  const yesNo = (value: boolean) => (value ? t("users.details.yes") : t("users.details.no"));
  const blocked = yesNo(user.is_blocked);
  const trialAvailable = user.is_trial_available ? t("users.details.trialYes") : t("users.details.trialNo");
  const createdAt = user.created_at ? formatDateTime(user.created_at, i18n.language) : undefined;
  const language = languageName(user.language, i18n.language);
  const canViewAdSource =
    currentUserState.kind === "ready" &&
    currentUserState.data.effective_permissions.includes("AD_LINKS_USER_ATTRIBUTION_VIEW");
  const [adSource] = useAsyncResource((signal) =>
    canViewAdSource ? getUserAdAttribution(user.id, signal) : Promise.resolve(null),
  );

  if (user.deleted_at) {
    // name and contacts are wiped on delete; only what history still refers to is left
    const deletedAt = formatDateTime(user.deleted_at, i18n.language);
    return (
      <Card variant="list" title={t("admins.details.sections.account")} icon={User}>
        <InfoRow icon={Hash} label={t("users.details.id")} copyValue={String(user.id)} mono>
          {user.id}
        </InfoRow>
        <InfoRow icon={CalendarDays} label={t("users.details.createdAt")} copyValue={createdAt} mono>
          {createdAt ?? dash}
        </InfoRow>
        <InfoRow icon={Trash2} label={t("users.deleted.at")} copyValue={deletedAt} mono>
          {deletedAt}
        </InfoRow>
      </Card>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <Card variant="list" title={t("admins.details.sections.account")} icon={User}>
        <InfoRow icon={Hash} label={t("users.details.id")} copyValue={String(user.id)} mono>
          {user.id}
        </InfoRow>
        <InfoRow icon={User} label={t("eventLog.detail.name")} copyValue={user.name}>
          <span className="truncate">{user.name}</span>
        </InfoRow>
        {user.login && (
          <InfoRow icon={KeyRound} label={t("users.details.login")} copyValue={user.login} mono>
            <span className="truncate">{user.login}</span>
          </InfoRow>
        )}
        <InfoRow icon={Mail} label={t("users.details.email")} copyValue={user.email ?? undefined} mono>
          {user.email ?? dash}
        </InfoRow>
        <InfoRow icon={Languages} label={t("users.details.language")} copyValue={language}>
          {language}
        </InfoRow>
        <InfoRow icon={Ban} label={t("admins.details.blocked")} copyValue={blocked}>
          <span className={user.is_blocked ? "text-error" : undefined}>{blocked}</span>
        </InfoRow>
        <InfoRow icon={Gift} label={t("users.details.trialAvailable")} copyValue={trialAvailable}>
          {trialAvailable}
        </InfoRow>
        <InfoRow icon={CalendarDays} label={t("users.details.createdAt")} copyValue={createdAt} mono>
          {createdAt ?? dash}
        </InfoRow>
        {user.referral_code && (
          <InfoRow icon={Link2} label={t("users.details.referralCode")} copyValue={user.referral_code} mono>
            {user.referral_code}
          </InfoRow>
        )}
        {canViewAdSource && (
          <InfoRow
            icon={Megaphone}
            label={t("users.details.adSource")}
            copyValue={adSource.kind === "ready" && adSource.data ? adSource.data.code : undefined}
          >
            {adSource.kind === "ready" && adSource.data ? (
              <>
                <span className="truncate">{adSource.data.name}</span>
                <Tag>{t(`advertising.channel.${adSource.data.channel}`)}</Tag>
              </>
            ) : (
              dash
            )}
          </InfoRow>
        )}
        {user.telegram_id !== null && (
          <div className="m-1 rounded-xl border border-white/[0.06] bg-white/[0.02] p-1">
            <h4 className={sectionTitleClassName}>
              <Send className="size-3.5" />
              {t("admins.details.sections.telegram")}
            </h4>
            <InfoRow icon={Hash} label={t("users.details.telegramId")} copyValue={String(user.telegram_id)} mono>
              {user.telegram_id}
            </InfoRow>
            <InfoRow
              icon={AtSign}
              label={t("users.details.username")}
              copyValue={user.username ? `@${user.username}` : undefined}
              mono
            >
              {user.username ? `@${user.username}` : dash}
            </InfoRow>
          </div>
        )}
      </Card>

      <div className="grid grid-cols-3 gap-3">
        <KpiTile label={t("users.details.points")} value={String(user.points)} />
        <KpiTile label={t("users.details.personalDiscount")} value={`${user.personal_discount}%`} />
        <KpiTile label={t("users.details.purchaseDiscount")} value={`${user.purchase_discount}%`} />
      </div>
    </div>
  );
}

export function SessionsTab({ userId }: { userId: number }) {
  const { t } = useTranslation();
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

  return (
    <Card variant="list">
      {state.kind === "loading" && <Spinner size="card" />}
      {state.kind === "error" && <p className="p-3 text-sm text-error">{t("sessions.loadError")}</p>}
      {state.kind === "ready" && <SessionList sessions={state.data} onRequestRevoke={setPendingRevoke} />}
      {pendingRevoke && (
        <ConfirmDialog
          title={t("sessions.revokeTitle")}
          message={t("sessions.revokeConfirm")}
          confirmLabel={t("sessions.revoke")}
          cancelLabel={t("sessions.cancel")}
          danger
          onConfirm={() => {
            void handleRevoke(pendingRevoke.id);
            setPendingRevoke(null);
          }}
          onCancel={() => setPendingRevoke(null)}
        />
      )}
    </Card>
  );
}

export function EventsTab({ actorId }: { actorId: number }) {
  const { t, i18n } = useTranslation();
  const [openedEntry, setOpenedEntry] = useState<EventLogEntry | null>(null);
  const [state, , setData] = useAsyncResource((signal) => listEventLog({ actorId, pageSize: EVENTS_PAGE_SIZE }, signal));
  const [page, setPage] = useState(1);
  const [isLoadingMore, setIsLoadingMore] = useState(false);

  const handleLoadMore = async () => {
    if (state.kind !== "ready") return;
    setIsLoadingMore(true);
    try {
      const result = await listEventLog({ actorId, page: page + 1, pageSize: EVENTS_PAGE_SIZE });
      setData({ items: [...state.data.items, ...result.items], total: result.total });
      setPage(page + 1);
    } catch {
      // keep current items; the button stays available to retry
    } finally {
      setIsLoadingMore(false);
    }
  };

  return (
    <Card variant="list">
      {state.kind === "loading" && <Spinner size="card" />}
      {state.kind === "error" && <p className="p-3 text-sm text-error">{t("eventLog.loadError")}</p>}
      {state.kind === "ready" && state.data.items.length === 0 && (
        <EmptyState text={t("admins.details.eventsEmpty")} />
      )}
      {state.kind === "ready" &&
        state.data.items.map((entry) => (
          <motion.button
            key={entry.id}
            type="button"
            onClick={() => setOpenedEntry(entry)}
            {...bounceTap(0.03)}
            className="flex w-full items-center gap-3 rounded-full px-2.5 py-2 text-left transition-colors hover:bg-white/[0.04]"
          >
            <span
              className="flex size-8 shrink-0 items-center justify-center rounded-full bg-white/[0.06] text-foreground"
            >
              <EventTypeIcon eventType={entry.event_type} className="size-3.5" />
            </span>
            <span className="min-w-0 flex-1 truncate text-[13px] font-medium text-foreground/90">
              {t(`eventLog.events.${entry.event_type}`)}
            </span>
            <span className="shrink-0 font-mono text-[12px] text-muted-foreground">
              {formatDateTime(entry.occurred_at, i18n.language)}
            </span>
          </motion.button>
        ))}
      {state.kind === "ready" && state.data.items.length < state.data.total && (
        <div className="px-2.5 py-1">
          <LoadMoreButton
            onClick={() => void handleLoadMore()}
            isLoading={isLoadingMore}
            shown={state.data.items.length}
            total={state.data.total}
          />
        </div>
      )}
      {openedEntry && <EventDetailDialog entry={openedEntry} onClose={() => setOpenedEntry(null)} />}
    </Card>
  );
}
