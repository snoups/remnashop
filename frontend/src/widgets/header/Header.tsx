import { ChevronDown, Menu, LogOut, RefreshCw, Sparkles, User as UserIcon, Wrench } from "lucide-react";
import { createPortal } from "react-dom";
import { TAB_HOVER_CLASS } from "@shared/ui/classes";
import { MobileMenu } from "@widgets/sidebar/MobileMenu";

import { AnimatePresence } from "motion/react";
import { useEffect, useRef, useState, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { matchPath, useLocation, useNavigate, useSearchParams } from "react-router-dom";

import { useBrandName } from "@entities/appearance/use-appearance";
import { useOnAccessSettingsSaved } from "@entities/settings/access-sync";
import { getAccessSettings } from "@entities/settings/api";
import { useCurrentUser, usePermissions } from "@entities/user/use-current-user";
import { useClickOutside } from "@shared/lib/use-click-outside";
import { useCloseOnScroll } from "@shared/lib/use-close-on-scroll";
import { usePageTitle } from "@shared/lib/use-page-title";
import { useRefreshSignal } from "@shared/lib/refresh-signal";
import { initials } from "@shared/lib/initials";
import { formatTime } from "@shared/lib/relative-time";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { ACCESS_SECTION_ID } from "@features/access-settings/AccessSettingsForm";
import { RecapDialog } from "@features/recap/RecapDialog";
import { HeaderSearch } from "@widgets/header/HeaderSearch";
import { NotificationsBell } from "@widgets/header/NotificationsBell";
import { LanguagePicker } from "@widgets/language-picker/LanguagePicker";
import { IconCircle } from "@shared/ui/glass/IconCircle";
import { IconButton } from "@shared/ui/IconButton";
import { PortalPopover } from "@shared/ui/PortalPopover";
import { Pressable } from "@shared/ui/Pressable";
import { NAV_ITEMS } from "@widgets/sidebar/nav-items";

// Popover grows out of its own top-right corner, toward the trigger.
const POPOVER_MOTION = {
  initial: { opacity: 0, scale: 0.85 },
  animate: { opacity: 1, scale: 1 },
  exit: { opacity: 0, scale: 0.85 },
  transition: { duration: 0.15, ease: "easeOut" },
} as const;

// two 36px items plus the popover padding
const USER_MENU_MAX_HEIGHT = 90;

interface HeaderProps {
  onLogout: () => void;
}

export function Header({ onLogout }: HeaderProps) {
  const [mobile, setMobile] = useState(() => window.matchMedia("(width < 768px)").matches);
  const [menuOpen, setMenuOpen] = useState(false);
  useEffect(() => {
    const query = window.matchMedia("(width < 768px)");
    const update = () => { setMobile(query.matches); setMenuOpen(false); };
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);
  const { t, i18n } = useTranslation();
  const brandName = useBrandName();
  const pageTitle = usePageTitle(brandName);
  const location = useLocation();
  const isOverviewPage = location.pathname === "/dashboard" || location.pathname === "/dashboard/";
  // the profile and the debug page have no sidebar link
  const PageIcon =
    NAV_ITEMS.find((item) => matchPath({ path: item.to, end: item.end ?? false }, location.pathname))?.icon ??
    (location.pathname.startsWith("/dashboard/profile") ? UserIcon : Wrench);
  const { refresh, updatedAt } = useRefreshSignal();
  const [isRefreshing, setIsRefreshing] = useState(false);
  const handleRefresh = useCallback(() => {
    refresh();
    setIsRefreshing(true);
    setTimeout(() => setIsRefreshing(false), 1000);
  }, [refresh]);
  const permissions = usePermissions();
  const userState = useCurrentUser();
  const login = userState.kind === "ready" ? userState.data.login : null;
  const role = userState.kind === "ready" ? userState.data.role : null;
  const [openPopover, setOpenPopover] = useState<"user" | "notifications" | null>(null);
  const [isRecapOpen, setIsRecapOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const notifRef = useRef<HTMLDivElement>(null);
  const menuPopoverRef = useRef<HTMLDivElement>(null);
  const notifPopoverRef = useRef<HTMLDivElement>(null);

  useClickOutside([menuRef, notifRef, menuPopoverRef, notifPopoverRef], openPopover !== null, () =>
    setOpenPopover(null),
  );
  useCloseOnScroll(openPopover !== null, [menuPopoverRef, notifPopoverRef], () => setOpenPopover(null));

  // a push notification click lands here with ?bell=open
  const [searchParams, setSearchParams] = useSearchParams();
  useEffect(() => {
    if (searchParams.get("bell") !== "open") return;
    setOpenPopover("notifications");
    const next = new URLSearchParams(searchParams);
    next.delete("bell");
    setSearchParams(next, { replace: true });
  }, [searchParams, setSearchParams]);


  const header = (
    <header className={mobile
      ? "fixed inset-x-2 top-[calc(8px+env(safe-area-inset-top))] z-30 flex h-16 items-center justify-between gap-3 rounded-card border border-glass-border bg-surface/50 px-3 text-foreground shadow-2xl backdrop-blur-[28px] backdrop-saturate-150"
      : "px-4 py-3 md:px-5 md:py-5"}>
      {/* desktop: one 48px glass capsule across the page, title in it, 36px items 6px in; mobile: the bar is the frame */}
      <div className={mobile ? "contents" : "glass-panel flex h-12 items-center justify-between gap-5 rounded-full p-1.5"}>
      <div className="flex min-w-0 items-center gap-2.5">
        {mobile && <IconButton size="9" tone="glass" onClick={() => { setOpenPopover(null); setMenuOpen(true); }}><Menu className="size-4" /></IconButton>}
        {!mobile && !isOverviewPage && <IconCircle icon={PageIcon} header />}
        {!mobile && isOverviewPage && (
          // the page icon is the refresh button: hover swaps it for the refresh arrows
          <Pressable
            type="button"
            onClick={handleRefresh}
            disabled={isRefreshing}
            className="group flex size-9 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] text-foreground transition-colors enabled:hover:bg-white/[0.08]"
          >
            {isRefreshing ? (
              <RefreshCw className="size-4 animate-spin" />
            ) : (
              <>
                <PageIcon className="size-4 group-hover:hidden" />
                <RefreshCw className="hidden size-4 group-hover:block" />
              </>
            )}
          </Pressable>
        )}
        <span className="truncate text-[17px] font-semibold tracking-tight text-foreground">{pageTitle}</span>
        {!mobile && isOverviewPage && updatedAt && (
          <span className="mt-1 shrink-0 whitespace-nowrap text-[11px] text-muted-foreground">
            {t("dashboard.updatedAt", { time: formatTime(updatedAt, i18n.language) })}
          </span>
        )}
      </div>

      <div className="flex min-w-0 flex-1 items-center justify-end gap-3 max-md:flex-none max-md:shrink-0 max-md:gap-2">
        {/* mobile keeps its bare bell and avatar */}
        <div className={mobile ? "contents" : "flex min-w-0 items-center gap-1"}>
        {!mobile && permissions.includes("ACCESS_SETTINGS_VIEW") && <MaintenanceBadge />}

        {!mobile && <HeaderSearch />}

        {!mobile && isOverviewPage && permissions.includes("OVERVIEW_RECAP_VIEW") && (
          <IconButton size="9" onClick={() => setIsRecapOpen(true)}>
            <Sparkles className="size-4" />
          </IconButton>
        )}

        {!mobile && <LanguagePicker capsule />}

        <div ref={notifRef} className="relative shrink-0">
          <NotificationsBell
            isOpen={openPopover === "notifications"}
            anchorRef={notifRef}
            popoverRef={notifPopoverRef}
            onToggle={() => setOpenPopover((open) => (open === "notifications" ? null : "notifications"))}
            onClose={() => setOpenPopover(null)}
            capsule={!mobile}
          />
        </div>

        {!mobile && <span className="mx-1 h-5 w-px shrink-0 bg-white/[0.08]" />}

        <div ref={menuRef} className="relative shrink-0">
          <Pressable
            type="button"
            onClick={() => setOpenPopover((open) => (open === "user" ? null : "user"))}
            className="group relative isolate flex h-9 items-center gap-2.5 rounded-full pr-1 md:pl-0.5 md:pr-2.5"
          >
            <span
              className={TAB_HOVER_CLASS}
            />
            <div className="glass-control relative z-10 flex size-8.5 shrink-0 items-center justify-center rounded-full text-[12px] font-semibold text-foreground md:size-8">
              {login ? initials(login) : <UserIcon className="size-4" />}
            </div>
            <div className="relative z-10 hidden text-left leading-tight md:block">
              <span className="block text-[13px] font-semibold text-foreground">{login ?? t("header.account")}</span>
              {role && <span className="block text-[12px] text-muted-foreground">{t(`roles.${role}`)}</span>}
            </div>
            <ChevronDown className={`relative z-10 hidden size-3.5 text-muted-foreground transition-transform md:block ${openPopover === "user" ? "rotate-180" : ""}`} />
          </Pressable>

          <PortalPopover
            open={openPopover === "user"}
            triggerRef={menuRef}
            popoverRef={menuPopoverRef}
            align="right"
            maxHeight={USER_MENU_MAX_HEIGHT}
            {...POPOVER_MOTION}
            glass
            // 12px off its trigger, like the header's other menus
            extraGap={4}
            className="w-48 p-1.5"
          >
            <Pressable as="link"
              to="/dashboard/profile"
              onClick={() => setOpenPopover(null)}
              className="flex h-9 items-center gap-2.5 rounded-popover-item px-2.5 text-[13px] font-medium text-foreground transition-colors hover:bg-white/[0.07]"
            >
              <UserIcon className="size-4 shrink-0" />
              {t("header.profile")}
            </Pressable>
            <Pressable
              type="button"
              onClick={onLogout}
              className="flex h-9 w-full items-center gap-2.5 rounded-popover-item px-2.5 text-left text-[13px] font-medium text-error transition-colors hover:bg-white/[0.07]"
            >
              <LogOut className="size-4 shrink-0" />
              {t("header.logout")}
            </Pressable>
          </PortalPopover>
        </div>
        </div>
      </div>
      </div>
    </header>
  );
  return (
    <>
      {mobile ? createPortal(header, document.body) : header}
      <AnimatePresence>
        {mobile && menuOpen && <MobileMenu key="mobile-menu" onClose={() => setMenuOpen(false)} />}
      </AnimatePresence>
      {isRecapOpen && <RecapDialog onClose={() => setIsRecapOpen(false)} />}
    </>
  );
}

function MaintenanceBadge() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [state, , setData] = useAsyncResource(getAccessSettings);
  useOnAccessSettingsSaved(setData);
  if (state.kind !== "ready" || state.data.mode !== "RESTRICTED") return null;
  return (
    // the capsule's first item, 36px like the rest; leads to the switch that set it
    <Pressable
      onClick={() => navigate(`/dashboard/settings#${ACCESS_SECTION_ID}`)}
      className="flex h-9 shrink-0 items-center gap-2 rounded-full px-3.5 text-[13px] font-medium text-warning transition-colors hover:bg-white/[0.06]"
    >
      <span className="size-1.5 shrink-0 rounded-full bg-current" />
      {t("header.maintenance")}
    </Pressable>
  );
}
