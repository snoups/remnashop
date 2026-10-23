import { LogOut } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { SessionsForm } from "@features/account-sessions/SessionsForm";
import { NotificationChannelsForm } from "@features/notification-settings/NotificationChannelsForm";
import { ConnectedAccountsForm } from "@features/oauth-accounts/ConnectedAccountsForm";
import { EditProfileDialog } from "@features/profile-edit/EditProfileDialog";
import { SecurityForm } from "@features/account-security/SecurityForm";
import { logout } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { clearAccessToken } from "@shared/lib/token-storage";
import { initials } from "@shared/lib/initials";
import { ErrorState } from "@shared/ui/EmptyState";
import { Spinner } from "@shared/ui/Spinner";
import { disablePushOnSignOut } from "@entities/notifications/push-api";
import { useCurrentUser } from "@entities/user/use-current-user";
import { Button } from "@shared/ui/Button";
import { Card } from "@shared/ui/Card";

export function ProfilePage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const state = useCurrentUser();

  const handleLogout = async () => {
    await disablePushOnSignOut();
    if (!(await logout())) toast.error(t("auth.errors.logoutNotConfirmed"));
    clearAccessToken();
    navigate("/", { replace: true });
  };


  return (
    <div className="flex flex-col gap-6">
      <Card>
        {state.kind === "loading" && <Spinner />}
        {state.kind === "error" && <ErrorState text={t("common.loadError")} />}
        {state.kind === "ready" && (
          <div className="flex items-center gap-4">
            <div className="flex size-14 shrink-0 items-center justify-center rounded-full bg-foreground text-[18px] font-bold text-canvas">
              {initials(state.kind === "ready" ? state.data.login : null)}
            </div>
            <div className="min-w-0 flex-1">
              <div className="truncate text-base font-bold text-foreground">{state.data.name}</div>
              <div className="truncate text-[13px] text-muted-foreground">
                {state.data.login ?? t("header.account")}
              </div>
            </div>
            <span className="flex h-9 shrink-0 items-center rounded-full border border-transparent bg-accent px-3 text-[12.5px] font-semibold text-primary">
              {t(`roles.${state.data.role}`)}
            </span>
            <EditProfileDialog name={state.data.name} login={state.data.login} />
            <Button
              variant="danger"
              type="button"
              onClick={handleLogout}
            >
              <LogOut className="size-3.5" />
              {t("header.logout")}
            </Button>
          </div>
        )}
      </Card>

      <ConnectedAccountsForm />
      <NotificationChannelsForm />
      <SecurityForm />
      <SessionsForm />
    </div>
  );
}
