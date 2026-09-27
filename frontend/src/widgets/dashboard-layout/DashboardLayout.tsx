import { Suspense, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Outlet, useNavigate } from "react-router-dom";

import { logout } from "@shared/api/http";
import { CurrentUserProvider } from "@entities/user/CurrentUserProvider";
import { toast } from "@shared/lib/toast";
import { clearAccessToken } from "@shared/lib/token-storage";
import { RefreshSignalContext } from "@shared/lib/refresh-signal";
import { useCurrentUser } from "@entities/user/use-current-user";
import { Header } from "@widgets/header/Header";
import { ServerError, ServerUnreachable } from "@widgets/server-error/ServerError";
import { Sidebar } from "@widgets/sidebar/Sidebar";

function DashboardShell({ onLogout }: { onLogout: () => void }) {
  const userState = useCurrentUser();
  const [refreshToken, setRefreshToken] = useState(0);
  const refreshSignal = useMemo(
    () => ({ token: refreshToken, refresh: () => setRefreshToken((n) => n + 1) }),
    [refreshToken],
  );

  if (userState.kind === "error") {
    return userState.isNetworkError ? <ServerUnreachable /> : <ServerError />;
  }

  return (
    <RefreshSignalContext.Provider value={refreshSignal}>
      <div className="mx-auto flex h-screen max-w-[1280px] text-foreground">
        <Sidebar />
        <div className="my-3 mr-3 flex flex-1 flex-col overflow-hidden rounded-3xl border border-glass-border bg-surface/50 shadow-2xl backdrop-blur-[28px] backdrop-saturate-150">
          <Header onLogout={onLogout} />
          <main className="scroll-fade-top flex flex-1 flex-col overflow-y-auto [scrollbar-gutter:stable] px-8 pb-8 pt-4">
            <Suspense fallback={null}>
              <Outlet />
            </Suspense>
          </main>
          {/* Dialogs portal here, not into `main` -- `main`'s `mask-image`
              (scroll-fade-top) makes it a containing block for `position:
              fixed`, which would shrink a dialog's fixed backdrop down to
              `main`'s own box and leave the header undimmed. This node sits
              outside `main` but still inside this wrapper's `backdrop-blur`,
              so dialogs keep the wrapper as their containing block instead --
              same look as before the scroll fade was added. */}
          <div id="dialog-root" />
        </div>
      </div>
    </RefreshSignalContext.Provider>
  );
}

export function DashboardLayout() {
  const { t } = useTranslation();
  const navigate = useNavigate();

  const handleLogout = async () => {
    if (!(await logout())) toast.error(t("auth.errors.logoutNotConfirmed"));
    clearAccessToken();
    navigate("/", { replace: true });
  };

  return (
    <CurrentUserProvider>
      <DashboardShell onLogout={handleLogout} />
    </CurrentUserProvider>
  );
}
