import { OAuthSettingsForm } from "@features/oauth-settings/OAuthSettingsForm";
import { ShopSettingsForm } from "@features/shop-settings/ShopSettingsForm";

export function GeneralSettingsPage() {
  return (
    <>
      <OAuthSettingsForm />
      <ShopSettingsForm />
    </>
  );
}
