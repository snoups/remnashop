import { AnimatePresence, motion } from "motion/react";
import { Suspense, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { matchPath, Navigate, useLocation, useNavigate, useOutlet } from "react-router-dom";

import { logout } from "@shared/api/http";
import { CurrentUserProvider } from "@entities/user/CurrentUserProvider";
import { PasswordChangeRequired } from "@features/password-change-required/PasswordChangeRequired";
import type { DASHBOARD_INTRO_STATE } from "@shared/lib/dashboard-intro";
import { useSidebarCollapsed } from "@shared/lib/sidebar-collapse";
import { toast } from "@shared/lib/toast";
import { clearAccessToken } from "@shared/lib/token-storage";
import { RefreshSignalContext } from "@shared/lib/refresh-signal";
import { useCurrentUser, usePermissions } from "@entities/user/use-current-user";
import { BottomNav } from "@widgets/bottom-nav/BottomNav";
import { EntityDialogHost } from "@widgets/entity-dialog-host/EntityDialogHost";
import { Header } from "@widgets/header/Header";
import { ServerError, ServerUnreachable } from "@widgets/server-error/ServerError";
import { NAV_ITEMS } from "@widgets/sidebar/nav-items";
import { Sidebar } from "@widgets/sidebar/Sidebar";
import { Spinner } from "@shared/ui/Spinner";

// Keyed by the first segment under /dashboard, so switching tabs inside
// settings doesn't fade the whole page. useOutlet() instead of <Outlet /> keeps
// the exiting page rendering its own route while it fades out.
function AnimatedOutlet() {
  const location = useLocation();
  const outlet = useOutlet();
  const permissions = usePermissions();
  const section = location.pathname.split("/")[2] ?? "";

  // a page whose sidebar link is hidden is off limits by URL too
  const gate = NAV_ITEMS.find(
    (item) => item.permission && matchPath({ path: item.to, end: false }, location.pathname),
  )?.permission;
  if (gate && !permissions.includes(gate)) {
    return <Navigate to="/dashboard" replace />;
  }

  return (
    <AnimatePresence mode="wait" initial={false}>
      <motion.div
        key={section}
        className="flex flex-1 flex-col"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1, transition: { duration: 0.18, ease: "easeOut" } }}
        exit={{ opacity: 0, transition: { duration: 0.15, ease: "easeIn" } }}
      >
        <Suspense fallback={null}>{outlet}</Suspense>
      </motion.div>
    </AnimatePresence>
  );
}

interface DashboardShellProps {
  onLogout: () => void;
  isLeaving: boolean;
  onLeft: () => void;
}

function DashboardShell({ onLogout, isLeaving, onLeft }: DashboardShellProps) {
  const userState = useCurrentUser();
  const isSidebarCollapsed = useSidebarCollapsed();
  const location = useLocation();
  const isIntro = (location.state as typeof DASHBOARD_INTRO_STATE | null)?.intro === true;
  const [refreshToken, setRefreshToken] = useState(0);
  const refreshSignal = useMemo(
    () => ({ token: refreshToken, refresh: () => setRefreshToken((n) => n + 1) }),
    [refreshToken],
  );

  if (userState.kind === "error") {
    return userState.isNetworkError ? <ServerUnreachable /> : <ServerError />;
  }
  // Pages read permissions on mount; rendered before /users/me answers they see
  // none, fetch with the wrong filters and flash their buttons in a beat later.
  if (userState.kind === "loading") {
    return <Spinner className="h-dvh" />;
  }
  if (userState.data.password_change_required) {
    return <PasswordChangeRequired />;
  }

  return (
    <RefreshSignalContext.Provider value={refreshSignal}>
      <EntityDialogHost>
      <motion.div
        // A collapsed sidebar gives its 176px (w-62 - 72px) back by narrowing the
        // shell, not widening the card, on the sidebar's own timing, so the card
        // keeps its width (both ends use min() to stay linear on narrow screens).
        className={`mx-auto flex h-dvh max-w-[min(1280px,100%)] flex-col text-foreground transition-[max-width] duration-200 ease-out md:h-screen md:flex-row ${
          isSidebarCollapsed ? "xl:max-w-[calc(min(1280px,100%)-11rem)]" : ""
        }`}
        initial={isIntro ? { opacity: 0 } : false}
        animate={{ opacity: isLeaving ? 0 : 1 }}
        transition={isLeaving ? { duration: 0.3, ease: "easeIn" } : { duration: 0.35, ease: "easeOut" }}
        onAnimationComplete={() => isLeaving && onLeft()}
      >
        <Sidebar />
        <motion.div
          className="mx-2 mt-2 flex min-h-0 flex-1 md:mx-0 md:my-3 md:mr-3 flex-col overflow-hidden rounded-3xl border border-glass-border bg-surface/50 shadow-2xl backdrop-blur-[28px] backdrop-saturate-150"
          initial={isIntro ? { opacity: 0, y: 14 } : false}
          animate={isLeaving ? { opacity: 0, y: 14 } : { opacity: 1, y: 0 }}
          transition={isLeaving ? { duration: 0.25, ease: "easeIn" } : { delay: 0.1, duration: 0.4, ease: [0.2, 0.8, 0.2, 1] }}
        >
          <Header onLogout={onLogout} />
          {/* the stable gutter's 10px comes out of the right padding, like dialog bodies (app/styles.css) */}
          <main className="scroll-fade-top flex flex-1 flex-col overflow-y-auto [scrollbar-gutter:stable] pb-6 pl-4 pr-[calc(1rem-10px)] pt-2 md:pb-8 md:pl-8 md:pr-[calc(2rem-10px)] md:pt-4">
            <AnimatedOutlet />
          </main>
          {/* dialogs portal here, not into `main` (see DialogPortal) */}
          <div id="dialog-root" />
        </motion.div>
        <BottomNav />
      </motion.div>
      </EntityDialogHost>
    </RefreshSignalContext.Provider>
  );
}

export function DashboardLayout() {
  const { t } = useTranslation();
  const navigate = useNavigate();

  const [isLeaving, setIsLeaving] = useState(false);

  const handleLogout = async () => {
    if (!(await logout())) toast.error(t("auth.errors.logoutNotConfirmed"));
    setIsLeaving(true);
  };

  // token is cleared only once the fade-out ends, so nothing mid-animation hits a 401
  const handleLeft = () => {
    clearAccessToken();
    navigate("/", { replace: true });
  };

  return (
    <CurrentUserProvider>
      <DashboardShell onLogout={handleLogout} isLeaving={isLeaving} onLeft={handleLeft} />
    </CurrentUserProvider>
  );
}
