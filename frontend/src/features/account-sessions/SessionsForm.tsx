import { LaptopMinimal } from "lucide-react";
import { useTranslation } from "react-i18next";

import { SessionsPanel } from "@features/account-sessions/SessionsPanel";
import { Card } from "@shared/ui/Card";

export function SessionsForm() {
  const { t } = useTranslation();

  return (
    <Card>
      <div className="flex items-center gap-2.5">
        <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] text-foreground backdrop-blur-md">
          <LaptopMinimal className="size-4" />
        </div>
        <div>
          <h2 className="text-sm font-bold text-foreground">{t("sessions.title")}</h2>
          <p className="mt-0.5 text-[12.5px] text-muted-foreground">{t("sessions.description")}</p>
        </div>
      </div>

      <div className="-mx-4 mt-4 border-t border-white/[0.07]" />

      <div className="mt-4">
        <SessionsPanel />
      </div>
    </Card>
  );
}
