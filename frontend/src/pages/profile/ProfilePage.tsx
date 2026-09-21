import { LogOut } from "lucide-react";
import { motion } from "motion/react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { SessionsForm } from "@features/account-sessions/SessionsForm";
import { ConnectedAccountsForm } from "@features/oauth-accounts/ConnectedAccountsForm";
import { EditProfileDialog } from "@features/profile-edit/EditProfileDialog";
import { SecurityForm } from "@features/account-security/SecurityForm";
import { logout } from "@shared/api/http";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { toast } from "@shared/lib/toast";
import { clearAccessToken } from "@shared/lib/token-storage";
import { Spinner } from "@shared/ui/Spinner";
import { useCurrentUser } from "@entities/user/use-current-user";

export function ProfilePage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const bounceStrength = useBounceStrength();
  const state = useCurrentUser();

  const handleLogout = async () => {
    if (!(await logout())) toast.error(t("auth.errors.logoutNotConfirmed"));
    clearAccessToken();
    navigate("/", { replace: true });
  };

  const initials = state.kind === "ready" ? (state.data.login ?? "?").slice(0, 2).toUpperCase() : "?";

  return (
    <div className="flex flex-col gap-6">
      <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-5">
        {state.kind === "loading" && <Spinner />}
        {state.kind === "error" && <p className="text-sm text-error">{t("profile.loadError")}</p>}
        {state.kind === "ready" && (
          <div className="flex items-center gap-4">
            <div className="flex size-14 shrink-0 items-center justify-center rounded-full bg-foreground text-[18px] font-bold text-canvas">
              {initials}
            </div>
            <div className="min-w-0 flex-1">
              <div className="truncate text-base font-bold text-foreground">{state.data.name}</div>
              <div className="truncate text-[13px] text-muted-foreground">
                {state.data.login ?? t("header.account")}
              </div>
            </div>
            <span className="shrink-0 rounded-full bg-accent px-3 py-1.5 text-[12px] font-semibold text-primary">
              {t(`roles.${state.data.role}`)}
            </span>
            <EditProfileDialog name={state.data.name} login={state.data.login} />
            <motion.button
              type="button"
              onClick={handleLogout}
              {...bounceTap(bounceStrength)}
              className="flex shrink-0 items-center gap-2 rounded-full border border-border px-3 py-1.5 text-[12px] font-semibold text-error transition-colors hover:bg-error/10"
            >
              <LogOut className="size-3.5" />
              {t("header.logout")}
            </motion.button>
          </div>
        )}
      </div>

      <ConnectedAccountsForm />
      <SecurityForm />
      <SessionsForm />
    </div>
  );
}
