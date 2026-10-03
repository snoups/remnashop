import { LaptopMinimal } from "lucide-react";
import { useTranslation } from "react-i18next";

import { SessionsPanel } from "@features/account-sessions/SessionsPanel";
import { Card } from "@shared/ui/Card";
import { CardHeader } from "@shared/ui/CardHeader";

export function SessionsForm() {
  const { t } = useTranslation();

  return (
    <Card>
      <CardHeader
        icon={LaptopMinimal}
        title={t("sessions.title")}
        description={t("sessions.description")}
      />

      <div className="mt-4">
        <SessionsPanel />
      </div>
    </Card>
  );
}
