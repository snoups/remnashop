import { Bell, ChevronDown, LogOut, RefreshCw, User as UserIcon } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useRef, useState, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { Link, useLocation } from "react-router-dom";

import { useBrandName } from "@entities/appearance/use-appearance";
import { useCurrentUser } from "@entities/user/use-current-user";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { useClickOutside } from "@shared/lib/use-click-outside";
import { useCloseOnScroll } from "@shared/lib/use-close-on-scroll";
import { usePageTitle } from "@shared/lib/use-page-title";
import { useRefreshSignal } from "@shared/lib/refresh-signal";
import { BounceIcon } from "@shared/ui/BounceIcon";
import { HeaderSearch } from "@widgets/header/HeaderSearch";
import { LanguagePicker } from "@widgets/language-picker/LanguagePicker";

const MotionLink = motion.create(Link);

// Popover grows out of its own top-right corner, toward the trigger.
const POPOVER_MOTION = {
  initial: { opacity: 0, scale: 0.85 },
  animate: { opacity: 1, scale: 1 },
  exit: { opacity: 0, scale: 0.85 },
  transition: { duration: 0.15, ease: "easeOut" },
  style: { transformOrigin: "top right" },
} as const;

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

  useClickOutside([menuRef, notifRef], openPopover !== null, () => setOpenPopover(null));
  useCloseOnScroll(openPopover !== null, [menuRef, notifRef], () => setOpenPopover(null));

  const initials = (login ?? "?").slice(0, 2).toUpperCase();

  return (
    <header className="flex flex-wrap items-center justify-between gap-5 px-8 py-5">
      <div className="flex items-center gap-2.5">
        <span className="text-[21px] font-bold tracking-tight text-foreground">{pageTitle}</span>
        {isOverviewPage && (
          <motion.button
            type="button"
            onClick={handleRefresh}
            disabled={isRefreshing}
            aria-label={t("dashboard.refresh")}
            {...bounceTap(bounceStrength, 0.12)}
            className="flex size-8 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] text-muted-foreground transition-colors hover:bg-white/[0.08] hover:text-foreground disabled:cursor-not-allowed"
          >
            <RefreshCw className={`size-[15px] ${isRefreshing ? "animate-spin" : ""}`} />
          </motion.button>
        )}
      </div>

      <div className="flex flex-1 items-center justify-end gap-3.5">
        <HeaderSearch />

        <LanguagePicker />

        <div ref={notifRef} className="relative shrink-0">
          <motion.button
            type="button"
            onClick={() => setOpenPopover((open) => (open === "notifications" ? null : "notifications"))}
            aria-haspopup="menu"
            aria-expanded={openPopover === "notifications"}
            aria-label={t("header.notifications")}
            {...bounceTap(bounceStrength, 0.12)}
            className="flex size-9 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] text-muted-foreground transition-colors hover:bg-white/[0.08] hover:text-foreground"
          >
            <Bell className="size-[17px]" />
          </motion.button>

          <AnimatePresence>
            {openPopover === "notifications" && (
              <motion.div
                {...POPOVER_MOTION}
                className="absolute right-0 top-full z-30 mt-2 h-24 w-64 rounded-popover border border-white/[0.14] bg-popover/60 shadow-[0_24px_48px_-20px_rgba(4,8,20,0.6),inset_0_1px_0_rgba(232,236,251,0.16)] backdrop-blur-2xl backdrop-saturate-150"
              />
            )}
          </AnimatePresence>
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

          <AnimatePresence>
            {openPopover === "user" && (
              <motion.div
                {...POPOVER_MOTION}
                className="absolute right-0 top-full z-30 mt-2 w-48 rounded-popover border border-white/[0.14] bg-popover/60 p-1.5 shadow-[0_24px_48px_-20px_rgba(4,8,20,0.6),inset_0_1px_0_rgba(232,236,251,0.16)] backdrop-blur-2xl backdrop-saturate-150"
              >
                <MotionLink
                  to="/dashboard/profile"
                  onClick={() => setOpenPopover(null)}
                  className="flex items-center gap-2.5 rounded-full px-2.5 py-2 text-[13px] font-medium text-foreground transition-colors hover:bg-white/[0.07]"
                  initial="rest"
                  whileHover="hover"
                >
                  <BounceIcon icon={UserIcon} size={15} hoverSize={18.75} />
                  {t("header.profile")}
                </MotionLink>
                <motion.button
                  type="button"
                  onClick={onLogout}
                  className="flex w-full items-center gap-2.5 rounded-full px-2.5 py-2 text-left text-[13px] font-medium text-foreground transition-colors hover:bg-white/[0.07]"
                  initial="rest"
                  whileHover="hover"
                >
                  <BounceIcon icon={LogOut} size={15} hoverSize={18.75} />
                  {t("header.logout")}
                </motion.button>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </header>
  );
}
