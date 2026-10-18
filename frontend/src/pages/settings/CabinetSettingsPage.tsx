import { usePermissions } from "@entities/user/use-current-user";
import { CabinetAuthSettingsForm } from "@features/cabinet-auth-settings/CabinetAuthSettingsForm";
import { BulkEmailSettingsForm } from "@features/email-settings/BulkEmailSettingsForm";
import { EmailSettingsForm } from "@features/email-settings/EmailSettingsForm";

export function CabinetSettingsPage() {
  const permissions = usePermissions();
  return (
    <div className="flex flex-col gap-4">
      {permissions.includes("CABINET_AUTH_SETTINGS_VIEW") && <CabinetAuthSettingsForm />}
      {permissions.includes("EMAIL_SETTINGS_VIEW") && <EmailSettingsForm />}
      {permissions.includes("EMAIL_SETTINGS_VIEW") && <BulkEmailSettingsForm />}
    </div>
  );
}
