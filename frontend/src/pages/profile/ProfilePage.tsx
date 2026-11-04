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
import { LoadGate, LoadGateHold } from "@shared/lib/load-gate";
import { ErrorState } from "@shared/ui/glass/EmptyState";
import { Spinner } from "@shared/ui/Spinner";
import { disablePushOnSignOut } from "@entities/notifications/push-api";
import { ROLE_BADGE_TONE } from "@entities/admin/display";
import { useCurrentUser } from "@entities/user/use-current-user";
import { Badge } from "@shared/ui/Badge";
import { Button } from "@shared/ui/Button";

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
    // its own scroller: main's fade would dim the header card at rest. data-under-header: the header's
    // 20px padding moves into this one, where the fade (scroll-fade-gap) sits
    <div data-fills-main data-under-header className="relative flex flex-1 flex-col md:min-h-0 md:pr-[var(--scrollbar-size)] md:-mb-5">
      <div className="scroll-fade-y scroll-fade-gap page-scroll md:min-h-0 md:pt-5 md:scroll-pt-5 md:flex-1 md:overflow-y-auto [--fade-bottom-size:0px] [scrollbar-gutter:stable] max-md:[scrollbar-gutter:auto] max-md:[scrollbar-width:none] max-md:[&::-webkit-scrollbar]:hidden md:-mr-5 md:pb-5 md:pr-[calc(1.25rem-var(--scrollbar-size))]">
        <LoadGate>
          <LoadGateHold isLoading={state.kind === "loading"} />
          <div className="flex flex-col gap-5">
            <section className="glass-panel rounded-3xl p-4">
              {state.kind === "loading" && <Spinner />}
              {state.kind === "error" && <ErrorState text={t("common.loadError")} />}
              {state.kind === "ready" && (
                <div className="flex flex-wrap items-center gap-3">
                  <div className="glass-control flex size-14 shrink-0 items-center justify-center rounded-full text-[18px] font-semibold text-foreground">
                    {initials(state.data.login)}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex min-w-0 items-center gap-2">
                      <span className="truncate text-[15px] font-semibold tracking-tight text-foreground">{state.data.name}</span>
                      <Badge borderless tone={ROLE_BADGE_TONE[state.data.role]}>
                        {t(`roles.${state.data.role}`)}
                      </Badge>
                    </div>
                    <div className="truncate text-[12px] text-muted-foreground">{state.data.login ?? t("header.account")}</div>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <EditProfileDialog name={state.data.name} login={state.data.login} />
                    <Button variant="glassDanger" icon={LogOut} onClick={() => void handleLogout()}>
                      {t("header.logout")}
                    </Button>
                  </div>
                </div>
              )}
            </section>

            <ConnectedAccountsForm />
            <NotificationChannelsForm />
            <SecurityForm />
            <SessionsForm />
          </div>
        </LoadGate>
      </div>
    </div>
  );
}
