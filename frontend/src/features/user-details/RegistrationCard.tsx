import { Globe, Languages, Link2, LogIn, Monitor, SquareArrowRightEnter, Star } from "lucide-react";
import { useTranslation } from "react-i18next";

import { getUserRegistration } from "@entities/user/api";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { DialogCard } from "@shared/ui/glass/DialogCard";
import { InfoRow } from "@shared/ui/InfoRow";

export function RegistrationCard({ userId }: { userId: number }) {
  const { t } = useTranslation();
  const [state] = useAsyncResource((signal) => getUserRegistration(userId, signal), { deps: [userId] });
  // accounts older than registration tracking have no record: no card at all
  if (state.kind !== "ready" || state.data.registration === null) return null;
  const registration = state.data.registration;
  return (
    <DialogCard collapsible title={t("users.registration.title")} icon={LogIn}>
      <InfoRow icon={SquareArrowRightEnter} label={t("users.registration.source")}>
        {t(`users.registration.sources.${registration.source}`)}
      </InfoRow>
      {registration.start_payload && (
        <InfoRow icon={Link2} label={t("users.registration.startPayload")} copyValue={registration.start_payload} mono>
          <span className="truncate">{registration.start_payload}</span>
        </InfoRow>
      )}
      {registration.telegram_language_code && (
        <InfoRow icon={Languages} label={t("users.registration.telegramLanguage")} mono>
          {registration.telegram_language_code}
        </InfoRow>
      )}
      {registration.telegram_is_premium !== null && (
        <InfoRow icon={Star} label={t("users.registration.telegramPremium")}>
          {registration.telegram_is_premium ? t("common.yes") : t("common.no")}
        </InfoRow>
      )}
      {registration.ip_address && (
        <InfoRow icon={Globe} label={t("users.registration.ip")} copyValue={registration.ip_address} mono>
          {registration.ip_address}
        </InfoRow>
      )}
      {registration.browser && (
        <InfoRow
          icon={Monitor}
          label={t("users.registration.browser")}
          copyValue={registration.user_agent ?? undefined}
        >
          <span className="truncate">{registration.browser}</span>
        </InfoRow>
      )}
    </DialogCard>
  );
}
