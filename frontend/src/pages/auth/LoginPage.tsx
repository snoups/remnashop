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
import { OAUTH_PROVIDERS } from "@entities/auth/oauth";
import { useBrandName } from "@entities/appearance/use-appearance";
import { BrandMark } from "@entities/appearance/BrandMark";
import { DASHBOARD_INTRO_STATE } from "@shared/lib/dashboard-intro";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { useDocumentTitle } from "@shared/lib/use-document-title";
import { GLASS_STANDALONE_CARD_CLASS, SCREEN_TITLE_CLASS } from "@shared/ui/classes";
import { Spinner } from "@shared/ui/Spinner";
import { LabeledDivider } from "@shared/ui/LabeledDivider";
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
  const status = state.kind === "ready" && state.data.is_login_allowed ? state.data : null;
  const altCount = status
    ? OAUTH_PROVIDERS.filter((provider) => status.oauth_providers[provider]).length +
      Number(status.is_passkey_login_enabled)
    : 0;
  // 1-3 one per row, 4 in a 2x2 grid
  const isGrid = altCount === 4;
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
            className="flex w-full max-w-sm flex-col items-center gap-6"
            initial="leave"
            animate={isLeaving ? "leave" : "rest"}
            exit="leave"
            onAnimationComplete={(definition) => definition === "leave" && isLeaving && enterDashboard()}
          >
            {/* faded one by one: backdrop-filter sees nothing through a translucent parent */}
            <motion.div variants={CARD_VARIANTS} className="flex items-center gap-3">
              <BrandMark className="size-9 shrink-0 text-primary" />
              <h1 className={SCREEN_TITLE_CLASS}>{brandName}</h1>
            </motion.div>

            <motion.div variants={CARD_VARIANTS} className={`flex w-full flex-col gap-6 ${GLASS_STANDALONE_CARD_CLASS}`}>
            {state.kind === "loading" && <Spinner />}

            {state.kind === "ready" && state.data.is_register_allowed && (
              <BootstrapOwnerForm onSuccess={() => setIsWelcome(true)} />
            )}

            {status?.is_password_login_enabled && <LoginForm onSuccess={goToDashboard} />}

            {status && altCount > 0 && (
              <div className="flex w-full flex-col gap-3">
                {status.is_password_login_enabled && (
                  <LabeledDivider>{t("auth.oauth.or")}</LabeledDivider>
                )}

                <div className={isGrid ? "grid grid-cols-2 gap-2" : "grid grid-cols-1 gap-2"}>
                  <OAuthLoginButtons
                    oauthProviders={status.oauth_providers}
                    oidcDisplayName={status.oidc_display_name}
                    compact={isGrid}
                  />
                  {status.is_passkey_login_enabled && (
                    <PasskeyLoginButton onSuccess={goToDashboard} compact={isGrid} />
                  )}
                </div>
              </div>
            )}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
