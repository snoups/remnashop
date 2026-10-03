import { ChevronsLeft, ChevronsRight } from "lucide-react";
import { motion } from "motion/react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, NavLink } from "react-router-dom";

import { useBrandName } from "@entities/appearance/use-appearance";
import { BrandMark } from "@entities/appearance/BrandMark";
import { usePermissions } from "@entities/user/use-current-user";
import { bounceTap } from "@shared/lib/bounceState";
import { toggleSidebarCollapsed, useSidebarCollapsed } from "@shared/lib/sidebar-collapse";
import { BounceIcon } from "@shared/ui/BounceIcon";
import { HINT_BUBBLE_CLASS } from "@shared/ui/hint-bubble";
import { IconButton } from "@shared/ui/IconButton";
import { BuildInfoBadge } from "@widgets/build-info/BuildInfoBadge";
import { DonateButton } from "@widgets/build-info/DonateButton";
import { NAV_ITEMS } from "@widgets/sidebar/nav-items";
import type { NavItem } from "@widgets/sidebar/nav-items";
import { LABEL_CLASSNAME, SIDEBAR_PILL_CLASSNAME, SIDEBAR_PILL_SHAPE_CLASSNAME } from "@widgets/sidebar/nav-pill";

const MotionNavLink = motion.create(NavLink);

const linkClassName = ({ isActive }: { isActive: boolean }) =>
  isActive
    ? `relative isolate ${SIDEBAR_PILL_SHAPE_CLASSNAME} font-semibold text-primary`
    : SIDEBAR_PILL_CLASSNAME;

interface Hint {
  text: string;
  top: number;
  left: number;
}

function NavItemLink({
  item,
  tapProps,
  label,
  onHint,
}: {
  item: NavItem;
  tapProps: ReturnType<typeof bounceTap>;
  label: string;
  onHint: (hint: Hint | null) => void;
}) {
  const showHint = (event: { currentTarget: HTMLElement }) => {
    const rect = event.currentTarget.getBoundingClientRect();
    onHint({ text: label, top: rect.top + rect.height / 2, left: rect.right + 14 });
  };

  return (
    <MotionNavLink
      to={item.to}
      end={item.end}
      className={linkClassName}
      initial="rest"
      whileHover="hover"
      onPointerEnter={showHint}
      onPointerLeave={() => onHint(null)}
      onFocus={showHint}
      onBlur={() => onHint(null)}
      {...tapProps}
    >
      {({ isActive }) => (
        <>
          {/* one shared layoutId, so the highlight glides between rows instead of jumping */}
          {isActive && (
            <motion.span
              layoutId="sidebar-active-pill"
              className="absolute inset-0 -z-10 rounded-full bg-accent"
              transition={{ type: "spring", stiffness: 420, damping: 36 }}
            />
          )}
          <BounceIcon icon={item.icon} size={17} hoverSize={23.5} />
          <span className={LABEL_CLASSNAME}>{label}</span>
        </>
      )}
    </MotionNavLink>
  );
}

export function Sidebar() {
  const { t } = useTranslation();
  const brandName = useBrandName();
  const [hint, setHint] = useState<Hint | null>(null);
  // kept after leave so the bubble fades out in place instead of jumping
  const [lastHint, setLastHint] = useState<Hint | null>(null);
  const handleHint = (next: Hint | null) => {
    setHint(next);
    if (next) setLastHint(next);
  };
  const isCollapsed = useSidebarCollapsed();
  const permissions = usePermissions();
  const visibleItems = NAV_ITEMS.filter((item) => !item.permission || permissions.includes(item.permission));
  // `scale`, not width/height, so a pressed row never pushes its neighbours
  const tapProps = bounceTap();

  return (
    <aside
      data-expanded={isCollapsed ? undefined : ""}
      className="group/sidebar hidden h-screen w-[72px] shrink-0 flex-col overflow-y-auto overflow-x-hidden p-2.5 transition-[width,padding] duration-200 ease-out md:flex xl:data-expanded:w-62 xl:data-expanded:p-3.5"
    >
      <div className="flex flex-col items-center gap-2 pb-5 xl:group-data-expanded/sidebar:flex-row">
        <Link
          to="/dashboard"
          className="flex min-w-0 items-center justify-center gap-2.5 rounded-xl px-2 pt-1.5 xl:group-data-expanded/sidebar:flex-1 xl:group-data-expanded/sidebar:justify-start"
        >
          <BrandMark className="size-8 shrink-0 text-primary" />
          <div className={LABEL_CLASSNAME}>
            <span className="block text-[15px] font-bold leading-[22px] tracking-tight text-foreground">{brandName}</span>
            <span className="block text-[11px] font-medium leading-4 text-muted-foreground">{t("sidebar.tagline")}</span>
          </div>
        </Link>
        {/* pt matches the Link's, so the button lines up with the logo on whole pixels */}
        <div className="hidden xl:block xl:group-data-expanded/sidebar:pt-1.5">
          <IconButton
            size="8"
            bounce={0.12}
            initial="rest"
            whileHover="hover"
            onClick={toggleSidebarCollapsed}
          >
            <BounceIcon icon={isCollapsed ? ChevronsRight : ChevronsLeft} size={17} hoverSize={21.25} />
          </IconButton>
        </div>
      </div>

      <nav className="flex flex-col gap-0.5">
        {visibleItems.map((item) => (
          <NavItemLink key={item.key} item={item} tapProps={tapProps} label={t(`sidebar.${item.key}`)} onHint={handleHint} />
        ))}
      </nav>

      {/* Icon rail only; the expanded sidebar shows the labels already. Fixed,
          not the shared Tooltip's absolute bubble: the aside scrolls, so an
          absolute one would be clipped at its edge. */}
      {lastHint && (
        <span
          className={`${HINT_BUBBLE_CLASS} z-50 -translate-y-1/2 xl:group-data-expanded/sidebar:hidden`}
          style={{ position: "fixed", top: lastHint.top, left: lastHint.left, opacity: hint ? 1 : 0 }}
        >
          {lastHint.text}
        </span>
      )}

      <div className="mt-auto flex flex-col gap-0.5 border-t border-border pt-3.5">
        <BuildInfoBadge />
        <DonateButton />
      </div>
    </aside>
  );
}
