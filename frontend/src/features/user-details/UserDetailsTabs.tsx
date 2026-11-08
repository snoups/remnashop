import {
  AtSign,
  Ban,
  CalendarDays,
  Gift,
  Hash,
  KeyRound,
  Languages,
  Mail,
  Megaphone,
  Send,
  Trash2,
  User,
  UserPlus,
} from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { getUserAdAttribution } from "@entities/advertising/api";
import { getUserReferralStats } from "@entities/referrals/api";
import { listEventLogAfter } from "@entities/event-log/api";
import type { EventLogEntry } from "@entities/event-log/api";
import { eventTitle } from "@entities/event-log/describe-entry";
import { EventTypeIcon } from "@entities/event-log/EventTypeIcon";
import type { UserBase } from "@entities/user/api";
import { userContacts, userName, userNameField } from "@entities/user/display";
import { usePermissions } from "@entities/user/use-current-user";
import { SessionsPanel } from "@features/account-sessions/SessionsPanel";
import { EventDetailDialog } from "@features/event-details/EventDetailDialog";
import { BalanceTiles } from "@features/user-details/BalanceTiles";
import { LegalAcceptancesCard } from "@features/user-details/LegalAcceptancesCard";
import { RegistrationCard } from "@features/user-details/RegistrationCard";
import { formatDateTime } from "@shared/lib/relative-time";
import { usePaginatedList } from "@shared/lib/use-paginated-list";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { Badge } from "@shared/ui/Badge";
import { DialogCard } from "@shared/ui/glass/DialogCard";
import { EmptyState, ErrorState } from "@shared/ui/glass/EmptyState";
import { Row } from "@shared/ui/glass/Row";
import { InfoRow } from "@shared/ui/InfoRow";
import { LoadMoreButton } from "@shared/ui/LoadMoreButton";
import { Spinner } from "@shared/ui/Spinner";
import { Tag } from "@shared/ui/Tag";
import { SECTION_TITLE_CLASS } from "@shared/ui/classes";

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

/** onChanged makes points and discounts editable, permissions allowing */
export function ProfileTab({ user, onChanged }: { user: UserBase; onChanged?: (user: UserBase) => void }) {
  const { t, i18n } = useTranslation();
  // sans even in mono rows: the dash looks the same everywhere
  const none = <span className="font-sans">{t("common.none")}</span>;
  const yesNo = (value: boolean) => (value ? t("common.yes") : t("common.no"));
  const blocked = yesNo(user.is_blocked);
  const trialAvailable = user.is_trial_available ? t("users.details.trialYes") : t("users.details.trialNo");
  const createdAt = user.created_at ? formatDateTime(user.created_at, i18n.language) : undefined;
  const language = languageName(user.language, i18n.language);
  const permissions = usePermissions();
  const canViewAdSource = permissions.includes("AD_LINKS_USER_ATTRIBUTION_VIEW");
  const canViewReferrer = permissions.includes("REFERRALS_VIEW");
  const canViewRegistration = permissions.includes("USERS_REGISTRATION_VIEW");
  const canViewLegal = permissions.includes("LEGAL_ACCEPTANCES_VIEW");
  const [adSource] = useAsyncResource((signal) =>
    canViewAdSource ? getUserAdAttribution(user.id, signal) : Promise.resolve(null),
  );
  const [referralStats] = useAsyncResource((signal) =>
    canViewReferrer ? getUserReferralStats(user.id, signal) : Promise.resolve(null),
  );
  const referralData = referralStats.kind === "ready" ? referralStats.data : null;
  const referrer = referralData?.referrer;
  const referrerText = referrer
    ? [`${userName(referrer, t)} #${referrer.id}`, userContacts(referrer, t)].filter(Boolean).join(" · ")
    : referralData?.referrer_id != null
      ? `#${referralData.referrer_id}`
      : undefined;

  if (user.deleted_at) {
    // name and contacts are wiped on delete; only what history still refers to is left
    const deletedAt = formatDateTime(user.deleted_at, i18n.language);
    return (
      <DialogCard title={t("admins.details.sections.account")} icon={User}>
        <InfoRow icon={Hash} label={t("users.details.id")} copyValue={String(user.id)} mono>
          {user.id}
        </InfoRow>
        <InfoRow icon={CalendarDays} label={t("users.details.createdAt")} copyValue={createdAt} mono>
          {createdAt ?? none}
        </InfoRow>
        <InfoRow icon={Trash2} label={t("users.deleted.at")} copyValue={deletedAt} mono>
          {deletedAt}
        </InfoRow>
      </DialogCard>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <DialogCard title={t("admins.details.sections.account")} icon={User}>
        <InfoRow icon={Hash} label={t("users.details.id")} copyValue={String(user.id)} mono>
          {user.id}
        </InfoRow>
        <InfoRow icon={User} label={t("eventLog.detail.name")} copyValue={user.name || undefined}>
          <span className="truncate">{userNameField(user, t)}</span>
        </InfoRow>
        {user.login && (
          <InfoRow icon={KeyRound} label={t("users.details.login")} copyValue={user.login} mono>
            <span className="truncate">{user.login}</span>
          </InfoRow>
        )}
        <InfoRow icon={Mail} label={t("users.details.email")} copyValue={user.email ?? undefined} mono>
          <span className="truncate">{user.email ?? none}</span>
          {user.email_undeliverable_at && <Badge tone="error">{t("users.emailUndeliverable.badge")}</Badge>}
        </InfoRow>
        <InfoRow icon={Languages} label={t("users.details.language")} copyValue={language}>
          {language}
        </InfoRow>
        {/* blocking demotes first, so staff are never blocked */}
        {user.role === "USER" && (
          <InfoRow icon={Ban} label={t("admins.details.blocked")} copyValue={blocked}>
            <span className={user.is_blocked ? "text-error" : undefined}>{blocked}</span>
          </InfoRow>
        )}
        <InfoRow icon={Gift} label={t("users.details.trialAvailable")} copyValue={trialAvailable}>
          {trialAvailable}
        </InfoRow>
        <InfoRow icon={CalendarDays} label={t("users.details.createdAt")} copyValue={createdAt} mono>
          {createdAt ?? none}
        </InfoRow>
        {user.referral_code && (
          <InfoRow icon={Hash} label={t("users.details.referralCode")} copyValue={user.referral_code} mono>
            {user.referral_code}
          </InfoRow>
        )}
        {canViewReferrer && (
          <InfoRow icon={UserPlus} label={t("referrals.stats.referrerLabel")} copyValue={referrerText}>
            {referrer ? (
              // contacts go to the clipboard only
              <>
                <span className="truncate">{userName(referrer, t)}</span>
                <span className="shrink-0 font-mono font-medium text-muted-foreground">#{referrer.id}</span>
              </>
            ) : (
              (referrerText ?? none)
            )}
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
              none
            )}
          </InfoRow>
        )}
        {user.telegram_id !== null && (
          <div className="mt-1 rounded-md border border-white/[0.08] bg-white/[0.02] p-1">
            <h4 className={SECTION_TITLE_CLASS}>
              <Send className="size-3.5" />
              {t("admins.details.sections.telegram")}
            </h4>
            <InfoRow icon={Send} label={t("users.details.telegramId")} copyValue={String(user.telegram_id)} mono>
              {user.telegram_id}
              {user.is_bot_blocked && <Badge tone="error">{t("users.botBlocked.badge")}</Badge>}
            </InfoRow>
            <InfoRow
              icon={AtSign}
              label={t("users.details.username")}
              copyValue={user.username ? `@${user.username}` : undefined}
              mono
            >
              {user.username ? `@${user.username}` : none}
            </InfoRow>
          </div>
        )}
      </DialogCard>

      {canViewRegistration && <RegistrationCard userId={user.id} />}
      {canViewLegal && <LegalAcceptancesCard userId={user.id} />}

      <BalanceTiles user={user} onChanged={onChanged} />
    </div>
  );
}

export function SessionsTab({ userId }: { userId: number }) {
  return (
    <DialogCard>
      <SessionsPanel userId={userId} />
    </DialogCard>
  );
}

// an admin's tab lists what they did, a customer's everything about them
export function EventsTab({ userId, by }: { userId: number; by: "actor" | "target" }) {
  const { t, i18n } = useTranslation();
  const [openedEntry, setOpenedEntry] = useState<EventLogEntry | null>(null);
  const { state, isLoadingMore, hasMore, loadMore } = usePaginatedList(
    (id: number, _page, signal, loaded?: EventLogEntry[]) =>
      listEventLogAfter(
        by === "actor"
          ? { actorId: id, pageSize: EVENTS_PAGE_SIZE }
          : { targetId: id, pageSize: EVENTS_PAGE_SIZE },
        loaded,
        signal,
      ),
    userId,
  );

  return (
    <DialogCard>
      {state.kind === "loading" && <Spinner size="card" />}
      {state.kind === "error" && <ErrorState text={t("common.loadError")} />}
      {state.kind === "ready" && state.items.length === 0 && (
        <EmptyState text={t("admins.details.eventsEmpty")} />
      )}
      {state.kind === "ready" &&
        state.items.map((entry) => (
          <Row
            key={entry.id}
            size="sm"
            glyph={<EventTypeIcon eventType={entry.event_type} className="size-4" />}
            label={eventTitle(entry, t)}
            onClick={() => setOpenedEntry(entry)}
          >
            <span className="font-mono text-[12px] text-muted-foreground">
              {formatDateTime(entry.occurred_at, i18n.language)}
            </span>
          </Row>
        ))}
      {state.kind === "ready" && hasMore && (
        <div className="px-2.5 py-1">
          <LoadMoreButton
            onClick={() => void loadMore()}
            isLoading={isLoadingMore}
            shown={state.items.length}
            total={state.total}
          />
        </div>
      )}
      {openedEntry && <EventDetailDialog entry={openedEntry} onClose={() => setOpenedEntry(null)} />}
    </DialogCard>
  );
}
