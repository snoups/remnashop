import { OAuthSettingsForm } from "@features/oauth-settings/OAuthSettingsForm";
import { ShopSettingsForm } from "@features/shop-settings/ShopSettingsForm";

export function GeneralSettingsPage() {
  return (
    <div className="flex flex-col gap-4">
      <OAuthSettingsForm />
      <ShopSettingsForm />
    </div>
  );
}
