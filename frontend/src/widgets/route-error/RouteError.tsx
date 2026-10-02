import { TriangleAlert } from "lucide-react";
import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { useRouteError } from "react-router-dom";

import { Button } from "@shared/ui/Button";
import { Card } from "@shared/ui/Card";
import { FULL_SCREEN_ACTION_CLASS, FullScreenMessage } from "@widgets/full-screen-message/FullScreenMessage";

function useLoggedRouteError() {
  const error = useRouteError();
  useEffect(() => console.error(error), [error]);
}

/** Root errorElement: whatever broke outside a dashboard page, the shell included. */
export function AppRouteError() {
  const { t } = useTranslation();
  useLoggedRouteError();

  return (
    <FullScreenMessage
      icon={TriangleAlert}
      iconClassName="text-error"
      title={t("errors.crashTitle")}
      description={t("errors.crashDescription")}
      action={
        <button type="button" onClick={() => window.location.reload()} className={FULL_SCREEN_ACTION_CLASS}>
          {t("errors.reload")}
        </button>
      }
    />
  );
}

/** errorElement of the dashboard pages: the sidebar and header stay, so another page is one click away. */
export function PageRouteError() {
  const { t } = useTranslation();
  useLoggedRouteError();

  return (
    <Card className="flex flex-col items-center gap-3 py-12 text-center">
      <TriangleAlert className="size-8 text-error" />
      <div>
        <h2 className="text-base font-bold text-foreground">{t("errors.crashTitle")}</h2>
        <p className="mt-1 text-sm text-muted-foreground">{t("errors.crashDescription")}</p>
      </div>
      <Button variant="accent" onClick={() => window.location.reload()}>
        {t("errors.reload")}
      </Button>
    </Card>
  );
}
