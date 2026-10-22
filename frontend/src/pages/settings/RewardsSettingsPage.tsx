import { usePermissions } from "@entities/user/use-current-user";
import { LoyaltySettingsPage } from "@pages/settings/LoyaltySettingsPage";
import { ReferralSettingsPage } from "@pages/settings/ReferralSettingsPage";

export function RewardsSettingsPage() {
  const permissions = usePermissions();
  return (
    <div className="flex flex-col gap-4">
      {permissions.includes("LOYALTY_SETTINGS_VIEW") && <LoyaltySettingsPage />}
      {permissions.includes("REFERRALS_SETTINGS_VIEW") && <ReferralSettingsPage />}
    </div>
  );
}
