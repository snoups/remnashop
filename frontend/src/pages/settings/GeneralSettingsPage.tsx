import { usePermissions } from "@entities/user/use-current-user";
import { CabinetAuthSettingsForm } from "@features/cabinet-auth-settings/CabinetAuthSettingsForm";
import { EmailSettingsForm } from "@features/email-settings/EmailSettingsForm";
import { OAuthSettingsForm } from "@features/oauth-settings/OAuthSettingsForm";
import { ShopSettingsForm } from "@features/shop-settings/ShopSettingsForm";
import { WebPushSettingsForm } from "@features/web-push-settings/WebPushSettingsForm";

export function GeneralSettingsPage() {
  const permissions = usePermissions();
  return (
    <div className="flex flex-col gap-4">
      {permissions.includes("OAUTH_SETTINGS_VIEW") && <OAuthSettingsForm />}
      {permissions.includes("CABINET_AUTH_SETTINGS_VIEW") && <CabinetAuthSettingsForm />}
      {permissions.includes("EMAIL_SETTINGS_VIEW") && <EmailSettingsForm />}
      {permissions.includes("SHOP_SETTINGS_VIEW") && <ShopSettingsForm />}
      {permissions.includes("NOTIFICATION_SETTINGS_VIEW") && <WebPushSettingsForm />}
    </div>
  );
}
