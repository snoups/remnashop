import { AnimatePresence, motion, type Variants } from "motion/react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { BootstrapOwnerForm } from "@features/bootstrap-owner/BootstrapOwnerForm";
import { WelcomeDonateDialog } from "@features/bootstrap-owner/WelcomeDonateDialog";
import { LoginForm } from "@features/login/LoginForm";
import { OAuthLoginButtons } from "@features/oauth-login/OAuthLoginButtons";
import { PasskeyLoginButton } from "@features/passkey-login/PasskeyLoginButton";
import { getAuthStatus } from "@entities/auth/api";
import { useBrandName } from "@entities/appearance/use-appearance";
import { BrandMark } from "@entities/appearance/BrandMark";
import { DASHBOARD_INTRO_STATE } from "@shared/lib/dashboard-intro";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { useDocumentTitle } from "@shared/lib/use-document-title";
import { Spinner } from "@shared/ui/Spinner";
import { LanguagePicker } from "@widgets/language-picker/LanguagePicker";
import { ServerError, ServerUnreachable } from "@widgets/server-error/ServerError";

const CARD_VARIANTS: Variants = {
  rest: { opacity: 1, scale: 1, transition: { duration: 0.3, ease: "easeOut" } },
  leave: { opacity: 0, scale: 0.97, transition: { duration: 0.25, ease: "easeIn" } },
};

export function LoginPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [state] = useAsyncResource(getAuthStatus);
  const brandName = useBrandName();
  const [isWelcome, setIsWelcome] = useState(false);
  const [isLeaving, setIsLeaving] = useState(false);

  const isBootstrap = state.kind === "ready" && state.data.is_register_allowed;
  useDocumentTitle(brandName, t(isBootstrap ? "auth.bootstrapPageTitle" : "auth.loginPageTitle"));

  const goToDashboard = () => setIsLeaving(true);
  const enterDashboard = () => navigate("/dashboard", { replace: true, state: DASHBOARD_INTRO_STATE });

  if (state.kind === "error") {
    return state.isNetworkError ? <ServerUnreachable /> : <ServerError />;
  }

  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center gap-8 px-4">
      <div className="absolute right-4 top-4">
        <LanguagePicker />
      </div>

      <AnimatePresence mode="wait">
        {isWelcome ? (
          <WelcomeDonateDialog key="welcome" onContinue={enterDashboard} />
        ) : (
          <motion.div
            key="card"
            className="flex w-full max-w-sm flex-col items-center gap-8 rounded-2xl border border-glass-border bg-surface/40 p-8 shadow-2xl backdrop-blur-xl"
            initial="leave"
            animate={isLeaving ? "leave" : "rest"}
            variants={CARD_VARIANTS}
            exit="leave"
            onAnimationComplete={(definition) => definition === "leave" && isLeaving && enterDashboard()}
          >
            <div className="flex items-center gap-3" aria-label={t("app.title")}>
              <BrandMark className="size-9 shrink-0 text-primary" />
              <h1 className="text-2xl font-bold tracking-tight text-foreground">{brandName}</h1>
            </div>

            {state.kind === "loading" && <Spinner />}

            {state.kind === "ready" && state.data.is_register_allowed && (
              <BootstrapOwnerForm onSuccess={() => setIsWelcome(true)} />
            )}

            {state.kind === "ready" &&
              state.data.is_login_allowed &&
              state.data.is_password_login_enabled && <LoginForm onSuccess={goToDashboard} />}

            {state.kind === "ready" && state.data.is_login_allowed && (
              <OAuthLoginButtons
                oauthProviders={state.data.oauth_providers}
                oidcDisplayName={state.data.oidc_display_name}
              />
            )}

            {state.kind === "ready" &&
              state.data.is_login_allowed &&
              state.data.is_passkey_login_enabled && (
                <PasskeyLoginButton onSuccess={goToDashboard} />
              )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
