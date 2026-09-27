import { motion } from "motion/react";
import { useTranslation } from "react-i18next";
import { Link, NavLink } from "react-router-dom";

import { useBrandName } from "@entities/appearance/use-appearance";
import { BrandMark } from "@entities/appearance/BrandMark";
import { useCurrentUser } from "@entities/user/use-current-user";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { BounceIcon } from "@shared/ui/BounceIcon";
import { BuildInfoBadge } from "@widgets/build-info/BuildInfoBadge";
import { DonateButton } from "@widgets/build-info/DonateButton";
import { NAV_ITEMS } from "@widgets/sidebar/nav-items";
import type { NavItem } from "@widgets/sidebar/nav-items";
import { LABEL_CLASSNAME, SIDEBAR_PILL_CLASSNAME } from "@widgets/sidebar/nav-pill";

const MotionNavLink = motion.create(NavLink);

const linkClassName = ({ isActive }: { isActive: boolean }) =>
  isActive
    ? "flex items-center justify-center gap-2.5 rounded-full bg-accent py-2.5 pl-3.5 pr-2.5 text-[13.5px] font-semibold text-primary lg:justify-start"
    : SIDEBAR_PILL_CLASSNAME;

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

        {visibleItems.slice(1).map((item) => (
          <NavItemLink key={item.key} item={item} tapProps={tapProps} label={t(`sidebar.${item.key}`)} />
        ))}
      </nav>

      <div className="mt-auto flex flex-col gap-0.5 border-t border-border pt-3.5">
        <BuildInfoBadge />
        <DonateButton />
      </div>
    </aside>
  );
}
