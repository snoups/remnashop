import {
  Ban,
  Coins,
  CreditCard,
  Database,
  Gift,
  LayoutGrid,
  Layers,
  Link2,
  MessageSquare,
  ScrollText,
  Server,
  Settings,
  ShieldCheck,
  Tag,
  Ticket,
  Users,
} from "lucide-react";
import { motion } from "motion/react";
import type { ComponentType } from "react";
import { useTranslation } from "react-i18next";
import { Link, NavLink } from "react-router-dom";

import { useBrandName } from "@entities/appearance/use-appearance";
import { BrandMark } from "@entities/appearance/BrandMark";
import { useCurrentUser } from "@entities/user/use-current-user";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import type { Permission } from "@shared/types/rbac";
import { BounceIcon } from "@shared/ui/BounceIcon";
import { ExternalLinksRow } from "@widgets/build-info/ExternalLinksRow";

const MotionNavLink = motion.create(NavLink);

interface NavItem {
  key: string;
  to: string;
  icon: ComponentType<{ className?: string }>;
  end?: boolean;
  // Omitted means always visible (overview, settings) -- everything else is
  // gated behind the matching permission. ADMINS_MANAGE is never
  // grantable/revocable per-user (see GRANTABLE_PERMISSIONS on the backend),
  // always exactly "role is OWNER or SYSTEM", but checking the permission
  // here keeps this in step with the rest of the list and doesn't quietly
  // drop SYSTEM.
  permission?: Permission;
}

const NAV_ITEMS: NavItem[] = [
  { key: "overview", to: "/dashboard", icon: LayoutGrid, end: true },
  { key: "users", to: "/dashboard/users", icon: Users, permission: "USERS_VIEW" },
  { key: "blacklist", to: "/dashboard/blacklist", icon: Ban, permission: "BLACKLIST_VIEW" },
  { key: "subscriptions", to: "/dashboard/subscriptions", icon: Layers, permission: "SUBSCRIPTIONS_VIEW" },
  { key: "plans", to: "/dashboard/plans", icon: Tag, permission: "PLANS_VIEW" },
  { key: "promocodes", to: "/dashboard/promocodes", icon: Ticket, permission: "PROMOCODES_VIEW" },
  { key: "referrals", to: "/dashboard/referrals", icon: Gift, permission: "REFERRALS_SETTINGS_VIEW" },
  { key: "advertising", to: "/dashboard/advertising", icon: Link2, permission: "AD_LINKS_VIEW" },
  { key: "payments", to: "/dashboard/payments", icon: CreditCard, permission: "PAYMENTS_VIEW" },
  { key: "admins", to: "/dashboard/admins", icon: ShieldCheck, permission: "ADMINS_MANAGE" },
  { key: "pricing", to: "/dashboard/pricing", icon: Coins, permission: "PRICING_VIEW" },
  { key: "eventLog", to: "/dashboard/event-log", icon: ScrollText, permission: "EVENT_LOG_VIEW" },
  { key: "backups", to: "/dashboard/backups", icon: Database, permission: "BACKUPS_VIEW" },
  { key: "settings", to: "/dashboard/settings", icon: Settings },
];

const DISABLED_ITEMS: { key: string; icon: ComponentType<{ className?: string }> }[] = [
  { key: "servers", icon: Server },
  { key: "support", icon: MessageSquare },
];

const linkClassName = ({ isActive }: { isActive: boolean }) =>
  isActive
    ? "flex items-center justify-center gap-2.5 rounded-full bg-accent py-2.5 pl-3.5 pr-2.5 text-[13.5px] font-semibold text-primary lg:justify-start"
    : "flex items-center justify-center gap-2.5 rounded-full py-2.5 pl-3.5 pr-2.5 text-[13.5px] font-medium text-muted-foreground transition-colors hover:bg-white/[0.06] hover:text-foreground lg:justify-start";

// Below `lg` there's no room for text labels next to the icons — the sidebar
// collapses to an icon rail instead (matches DESKTOP_BREAKPOINT elsewhere).
const LABEL_CLASSNAME = "hidden lg:inline";

function NavItemLink({ item, tapProps, label }: { item: NavItem; tapProps: ReturnType<typeof bounceTap>; label: string }) {
  return (
    <MotionNavLink to={item.to} end={item.end} className={linkClassName} initial="rest" whileHover="hover" {...tapProps}>
      <BounceIcon icon={item.icon} size={17} hoverSize={23.5} />
      <span className={LABEL_CLASSNAME}>{label}</span>
    </MotionNavLink>
  );
}

export function Sidebar() {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const brandName = useBrandName();
  const userState = useCurrentUser();
  const permissions = userState.kind === "ready" ? userState.data.effective_permissions : [];
  const visibleItems = NAV_ITEMS.filter((item) => !item.permission || permissions.includes(item.permission));
  // Bounce via `scale` (transform), not width/height — transform is layout-inert,
  // so a pressed row never pushes its neighbours.
  const tapProps = bounceTap(bounceStrength);

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
        {visibleItems.slice(0, 1).map((item) => (
          <NavItemLink key={item.key} item={item} tapProps={tapProps} label={t(`sidebar.${item.key}`)} />
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

        {visibleItems.slice(1).map((item) => (
          <NavItemLink key={item.key} item={item} tapProps={tapProps} label={t(`sidebar.${item.key}`)} />
        ))}
      </nav>

      <div className="mt-auto flex flex-wrap gap-1 border-t border-border pt-3.5">
        <ExternalLinksRow />
      </div>
    </aside>
  );
}
