import { ChevronDown, LogOut, RefreshCw, User as UserIcon } from "lucide-react";
import { motion } from "motion/react";
import { useRef, useState, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { Link, useLocation } from "react-router-dom";

import { useBrandName } from "@entities/appearance/use-appearance";
import { useCurrentUser } from "@entities/user/use-current-user";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { toggleDebugBar } from "@shared/lib/debug-bar";
import { useClickOutside } from "@shared/lib/use-click-outside";
import { useCloseOnScroll } from "@shared/lib/use-close-on-scroll";
import { usePageTitle } from "@shared/lib/use-page-title";
import { useRefreshSignal } from "@shared/lib/refresh-signal";
import { BounceIcon } from "@shared/ui/BounceIcon";
import { HeaderSearch } from "@widgets/header/HeaderSearch";
import { NotificationsBell } from "@widgets/header/NotificationsBell";
import { LanguagePicker } from "@widgets/language-picker/LanguagePicker";
import { IconButton } from "@shared/ui/IconButton";
import { PortalPopover } from "@shared/ui/PortalPopover";

const MotionLink = motion.create(Link);

// Popover grows out of its own top-right corner, toward the trigger.
const POPOVER_MOTION = {
  initial: { opacity: 0, scale: 0.85 },
  animate: { opacity: 1, scale: 1 },
  exit: { opacity: 0, scale: 0.85 },
  transition: { duration: 0.15, ease: "easeOut" },
} as const;

// same as BuildInfoBadge's -- the title stands in for it where the sidebar is hidden
const LONG_PRESS_MS = 600;

// two 36px items plus the popover padding
const USER_MENU_MAX_HEIGHT = 90;

interface HeaderProps {
  onLogout: () => void;
}

export function Header({ onLogout }: HeaderProps) {
  const { t } = useTranslation();
  const brandName = useBrandName();
  const pageTitle = usePageTitle(brandName);
  const bounceStrength = useBounceStrength();
  const location = useLocation();
  const isOverviewPage = location.pathname === "/dashboard" || location.pathname === "/dashboard/";
  const { refresh } = useRefreshSignal();
  const [isRefreshing, setIsRefreshing] = useState(false);
  const handleRefresh = useCallback(() => {
    refresh();
    setIsRefreshing(true);
    setTimeout(() => setIsRefreshing(false), 1000);
  }, [refresh]);
  const userState = useCurrentUser();
  const login = userState.kind === "ready" ? userState.data.login : null;
  const role = userState.kind === "ready" ? userState.data.role : null;
  const [openPopover, setOpenPopover] = useState<"user" | "notifications" | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const notifRef = useRef<HTMLDivElement>(null);
  const menuPopoverRef = useRef<HTMLDivElement>(null);
  const notifPopoverRef = useRef<HTMLDivElement>(null);

  useClickOutside([menuRef, notifRef, menuPopoverRef, notifPopoverRef], openPopover !== null, () =>
    setOpenPopover(null),
  );
  useCloseOnScroll(openPopover !== null, [menuPopoverRef, notifPopoverRef], () => setOpenPopover(null));

  const longPressTimer = useRef<number | null>(null);
  const cancelLongPress = () => {
    if (longPressTimer.current !== null) clearTimeout(longPressTimer.current);
    longPressTimer.current = null;
  };
  const startLongPress = () => {
    cancelLongPress();
    longPressTimer.current = window.setTimeout(toggleDebugBar, LONG_PRESS_MS);
  };

  const initials = (login ?? "?").slice(0, 2).toUpperCase();

  return (
    <header className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 md:gap-5 md:px-8 md:py-5">
      <div className="flex items-center gap-2.5">
        <span
          onPointerDown={startLongPress}
          onPointerUp={cancelLongPress}
          onPointerLeave={cancelLongPress}
          onPointerCancel={cancelLongPress}
          onContextMenu={(event) => event.preventDefault()}
          className="select-none text-[21px] font-bold tracking-tight text-foreground md:select-auto"
        >
          {pageTitle}
        </span>
        {isOverviewPage && (
          <IconButton
            size="8"
            tone="glass"
            bounce={0.12}
            onClick={handleRefresh}
            disabled={isRefreshing}
            aria-label={t("dashboard.refresh")}
          >
            <RefreshCw className={`size-[15px] ${isRefreshing ? "animate-spin" : ""}`} />
          </IconButton>
        )}
      </div>

      <div className="flex flex-1 items-center justify-end gap-3.5">
        <HeaderSearch />

        <LanguagePicker />

        <div ref={notifRef} className="relative shrink-0">
          <NotificationsBell
            isOpen={openPopover === "notifications"}
            anchorRef={notifRef}
            popoverRef={notifPopoverRef}
            onToggle={() => setOpenPopover((open) => (open === "notifications" ? null : "notifications"))}
            onClose={() => setOpenPopover(null)}
          />
        </div>

        <div ref={menuRef} className="relative shrink-0 border-l border-border pl-3.5">
          <motion.button
            type="button"
            onClick={() => setOpenPopover((open) => (open === "user" ? null : "user"))}
            aria-haspopup="menu"
            aria-expanded={openPopover === "user"}
            {...bounceTap(bounceStrength, 0.05)}
            className="group relative isolate flex h-9 items-center gap-2.5 rounded-full pr-1"
          >
            <span
              aria-hidden
              className="absolute inset-0 rounded-full transition-colors group-hover:bg-white/[0.05]"
            />
            <div className="relative z-10 flex size-8.5 shrink-0 items-center justify-center rounded-full bg-foreground text-[12px] font-bold text-canvas">
              {login ? initials : <UserIcon className="size-4" />}
            </div>
            <div className="relative z-10 hidden text-left leading-tight sm:block">
              <span className="block text-[13px] font-semibold text-foreground">{login ?? t("header.account")}</span>
              {role && <span className="block text-[11.5px] text-muted-foreground">{t(`roles.${role}`)}</span>}
            </div>
            <ChevronDown className={`relative z-10 size-3.5 text-muted-foreground transition-transform ${openPopover === "user" ? "rotate-180" : ""}`} />
          </motion.button>

          <PortalPopover
            open={openPopover === "user"}
            triggerRef={menuRef}
            popoverRef={menuPopoverRef}
            align="right"
            maxHeight={USER_MENU_MAX_HEIGHT}
            {...POPOVER_MOTION}
            className="w-48 p-1.5"
          >
            <MotionLink
              to="/dashboard/profile"
              onClick={() => setOpenPopover(null)}
              className="flex h-9 items-center gap-2.5 rounded-popover-item px-2.5 text-[13px] font-medium text-foreground transition-colors hover:bg-white/[0.07]"
              initial="rest"
              whileHover="hover"
            >
              <BounceIcon icon={UserIcon} size={15} hoverSize={18.75} />
              {t("header.profile")}
            </MotionLink>
            <motion.button
              type="button"
              onClick={onLogout}
              className="flex h-9 w-full items-center gap-2.5 rounded-popover-item px-2.5 text-left text-[13px] font-medium text-error transition-colors hover:bg-white/[0.07]"
              initial="rest"
              whileHover="hover"
            >
              <BounceIcon icon={LogOut} size={15} hoverSize={18.75} />
              {t("header.logout")}
            </motion.button>
          </PortalPopover>
        </div>
      </div>
    </header>
  );
}
