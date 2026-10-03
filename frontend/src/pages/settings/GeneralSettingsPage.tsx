import { usePermissions } from "@entities/user/use-current-user";
import { OAuthSettingsForm } from "@features/oauth-settings/OAuthSettingsForm";
import { ShopSettingsForm } from "@features/shop-settings/ShopSettingsForm";

export function GeneralSettingsPage() {
  const permissions = usePermissions();
  return (
    <div className="flex flex-col gap-4">
      {permissions.includes("OAUTH_SETTINGS_VIEW") && <OAuthSettingsForm />}
      {permissions.includes("SHOP_SETTINGS_VIEW") && <ShopSettingsForm />}
    </div>
  );
}
