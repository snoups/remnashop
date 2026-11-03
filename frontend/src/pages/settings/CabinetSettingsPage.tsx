import { useState } from "react";

import { usePermissions } from "@entities/user/use-current-user";
import { CabinetAuthSettingsForm } from "@features/cabinet-auth-settings/CabinetAuthSettingsForm";
import { EmailSettingsForm } from "@features/email-settings/EmailSettingsForm";
import { ConnectGuideSettingsPage } from "@pages/settings/ConnectGuideSettingsPage";

export function CabinetSettingsPage() {
  const permissions = usePermissions();
  // the cabinet card shows whether SMTP is set up, so a save below refreshes it
  const [emailVersion, setEmailVersion] = useState(0);
  return (
    <div className="flex flex-col gap-5">
      {permissions.includes("CABINET_AUTH_SETTINGS_VIEW") && <CabinetAuthSettingsForm emailVersion={emailVersion} />}
      {permissions.includes("EMAIL_SETTINGS_VIEW") && <EmailSettingsForm onSaved={() => setEmailVersion((version) => version + 1)} />}
      {permissions.includes("CONNECT_GUIDE_VIEW") && <ConnectGuideSettingsPage />}
    </div>
  );
}
