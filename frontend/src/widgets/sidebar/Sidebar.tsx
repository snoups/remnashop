import {
  CreditCard,
  LayoutGrid,
  Layers,
  MessageSquare,
  ScrollText,
  Server,
  Settings,
  ShieldCheck,
  Tag,
  Users,
} from "lucide-react";
import { motion } from "motion/react";
import type { ComponentType } from "react";
import { useTranslation } from "react-i18next";
import { Link, NavLink } from "react-router-dom";

import { useBrandName } from "@entities/appearance/use-appearance";
import { BrandMark } from "@entities/appearance/BrandMark";
import { useCurrentUser } from "@entities/user/use-current-user";
import { useBounceStrength } from "@shared/lib/bounceState";
import { BounceIcon } from "@shared/ui/BounceIcon";
import { ExternalLinksRow } from "@widgets/build-info/ExternalLinksRow";

const MotionNavLink = motion.create(NavLink);

const NAV_LINKS: { key: string; to: string; icon: ComponentType<{ className?: string }> }[] = [
  { key: "overview", to: "/dashboard", icon: LayoutGrid },
];

const DISABLED_ITEMS: { key: string; icon: ComponentType<{ className?: string }> }[] = [
  { key: "subscriptions", icon: Layers },
  { key: "servers", icon: Server },
  { key: "payments", icon: CreditCard },
  { key: "plans", icon: Tag },
  { key: "support", icon: MessageSquare },
];

const linkClassName = ({ isActive }: { isActive: boolean }) =>
  isActive
    ? "flex items-center justify-center gap-2.5 rounded-full bg-accent py-2.5 pl-3.5 pr-2.5 text-[13.5px] font-semibold text-primary lg:justify-start"
    : "flex items-center justify-center gap-2.5 rounded-full py-2.5 pl-3.5 pr-2.5 text-[13.5px] font-medium text-muted-foreground transition-colors hover:bg-white/[0.06] hover:text-foreground lg:justify-start";

// Below `lg` there's no room for text labels next to the icons — the sidebar
// collapses to an icon rail instead (matches DESKTOP_BREAKPOINT elsewhere).
const LABEL_CLASSNAME = "hidden lg:inline";

export function Sidebar() {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const brandName = useBrandName();
  const userState = useCurrentUser();
  const isOwner = userState.kind === "ready" && userState.data.role === "OWNER";
  const permissions = userState.kind === "ready" ? userState.data.effective_permissions : [];
  // Bounce via `scale` (transform), not width/height — transform is layout-inert,
  // so a pressed row never pushes its neighbours.
  const tapProps = {
    whileTap: { scale: 1 + 0.05 * bounceStrength },
    transition: { type: "spring", stiffness: 500, damping: 15 },
  } as const;

  return (
    <aside className="flex h-screen w-[72px] shrink-0 flex-col overflow-y-auto p-2.5 lg:w-62 lg:p-3.5">
      <Link
        to="/dashboard"
        className="flex items-center justify-center gap-2.5 rounded-xl px-2 pb-5 pt-1.5 lg:justify-start"
      >
        <BrandMark className="size-8 shrink-0 text-primary" />
        <div className={LABEL_CLASSNAME}>
          <span className="block text-[15px] font-bold tracking-tight text-foreground">{brandName}</span>
          <span className="block text-[11px] font-medium text-muted-foreground">{t("sidebar.tagline")}</span>
        </div>
      </Link>

      <nav aria-label={t("header.dashboard")} className="flex flex-col gap-0.5">
        {NAV_LINKS.map(({ key, to, icon: Icon }) => (
          <MotionNavLink
            key={key}
            to={to}
            end={to === "/dashboard"}
            className={linkClassName}
            initial="rest"
            whileHover="hover"
            {...tapProps}
          >
            <BounceIcon icon={Icon} size={17} hoverSize={23.5} />
            <span className={LABEL_CLASSNAME}>{t(`sidebar.${key}`)}</span>
          </MotionNavLink>
        ))}

        {DISABLED_ITEMS.map(({ key, icon: Icon }) => (
          <span
            key={key}
            className="flex cursor-not-allowed items-center justify-center gap-2.5 rounded-full py-2.5 pl-3.5 pr-2.5 text-[13.5px] font-medium text-muted-foreground/40 lg:justify-start"
          >
            <Icon className="size-[17px] shrink-0" />
            <span className={LABEL_CLASSNAME}>{t(`sidebar.${key}`)}</span>
          </span>
        ))}

        {permissions.includes("USERS_VIEW") && (
          <MotionNavLink
            to="/dashboard/users"
            className={linkClassName}
            initial="rest"
            whileHover="hover"
            {...tapProps}
          >
            <BounceIcon icon={Users} size={17} hoverSize={23.5} />
            <span className={LABEL_CLASSNAME}>{t("sidebar.users")}</span>
          </MotionNavLink>
        )}

        {isOwner && (
          <MotionNavLink
            to="/dashboard/admins"
            className={linkClassName}
            initial="rest"
            whileHover="hover"
            {...tapProps}
          >
            <BounceIcon icon={ShieldCheck} size={17} hoverSize={23.5} />
            <span className={LABEL_CLASSNAME}>{t("sidebar.admins")}</span>
          </MotionNavLink>
        )}
        {permissions.includes("EVENT_LOG_VIEW") && (
          <MotionNavLink
            to="/dashboard/event-log"
            className={linkClassName}
            initial="rest"
            whileHover="hover"
            {...tapProps}
          >
            <BounceIcon icon={ScrollText} size={17} hoverSize={23.5} />
            <span className={LABEL_CLASSNAME}>{t("sidebar.eventLog")}</span>
          </MotionNavLink>
        )}

        <MotionNavLink
          to="/dashboard/settings"
          className={linkClassName}
          initial="rest"
          whileHover="hover"
          {...tapProps}
        >
          <BounceIcon icon={Settings} size={17} hoverSize={23.5} />
          <span className={LABEL_CLASSNAME}>{t("sidebar.settings")}</span>
        </MotionNavLink>
      </nav>

      <div className="mt-auto flex flex-wrap gap-1 border-t border-border pt-3.5">
        <ExternalLinksRow />
      </div>
    </aside>
  );
}
