import { TriangleAlert } from "lucide-react";
import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { useRouteError } from "react-router-dom";

import { Button } from "@shared/ui/Button";
import { Pressable } from "@shared/ui/Pressable";
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
      tone="error"
      title={t("errors.crashTitle")}
      description={t("errors.crashDescription")}
      action={
        <Pressable type="button" onClick={() => window.location.reload()} className={FULL_SCREEN_ACTION_CLASS}>
          {t("errors.reload")}
        </Pressable>
      }
    />
  );
}

/** errorElement of the dashboard pages: the sidebar and header stay, so another page is one click away. */
export function PageRouteError() {
  const { t } = useTranslation();
  useLoggedRouteError();

  return (
    // a glass card with the full-screen message's layout, smaller
    <div className="glass-panel flex flex-col items-center gap-4 rounded-3xl px-4 py-12 text-center">
      <span className="flex size-12 items-center justify-center rounded-full border border-error/40 bg-error/10 text-error">
        <TriangleAlert className="size-5" />
      </span>
      <div className="flex flex-col gap-1">
        <h2 className="text-[15px] font-semibold tracking-tight text-foreground">{t("errors.crashTitle")}</h2>
        <p className="text-[13px] text-muted-foreground">{t("errors.crashDescription")}</p>
      </div>
      <Button variant="glassSolid" onClick={() => window.location.reload()}>
        {t("errors.reload")}
      </Button>
    </div>
  );
}
