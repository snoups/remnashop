import { Bot, CreditCard, KeyRound, Palette, SlidersHorizontal } from "lucide-react";
import { motion } from "motion/react";
import type { ComponentType, MouseEvent } from "react";
import { useTranslation } from "react-i18next";
import { NavLink, Outlet, useMatch } from "react-router-dom";

import { useBounceStrength } from "@shared/lib/bounceState";
import { useCurrentUser } from "@entities/user/use-current-user";
import { BounceIcon } from "@shared/ui/BounceIcon";

const MotionNavLink = motion.create(NavLink);

// Re-navigating to the already-active tab still calls react-router's
// navigate() (even though the URL doesn't change), which resets Framer
// Motion's tap-gesture state on that link -- every tap after the first stops
// bouncing. Skipping navigation when already active keeps whileTap working.
function preventNavigationWhenActive(isActive: boolean) {
  return (event: MouseEvent) => {
    if (isActive) event.preventDefault();
  };
}

interface SettingsTabProps {
  to: string;
  end?: boolean;
  icon: ComponentType<{ className?: string }>;
  label: string;
  isActive: boolean;
  bounceStrength: number;
}

// The scale bounce lives on a separate background pill behind the icon/label,
// not on the link itself -- scaling the text via `transform` blurs it (same
// reasoning as BounceIcon avoiding transform for icons), so only the pill
// grows on tap while the content stays crisp and fixed-size.
function SettingsTab({ to, end, icon, label, isActive, bounceStrength }: SettingsTabProps) {
  return (
    <MotionNavLink
      to={to}
      end={end}
      onClick={preventNavigationWhenActive(isActive)}
      className="group relative isolate block rounded-full text-sm font-medium"
      initial="rest"
      whileHover="hover"
      whileTap="tap"
    >
      <motion.span
        aria-hidden
        variants={{ rest: { scale: 1 }, tap: { scale: 1 + 0.05 * bounceStrength } }}
        transition={{ type: "spring", stiffness: 500, damping: 15 }}
        className={`absolute inset-0 rounded-full transition-colors ${
          isActive ? "bg-accent" : "group-hover:bg-white/[0.06]"
        }`}
      />
      <span
        className={`relative z-10 flex items-center gap-1.5 px-4 py-2 ${
          isActive ? "text-primary" : "text-foreground"
        }`}
      >
        <BounceIcon icon={icon} size={16} hoverSize={20} />
        {label}
      </span>
    </MotionNavLink>
  );
}

export function SettingsPage() {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const userState = useCurrentUser();
  const isOwner = userState.kind === "ready" && userState.data.role === "OWNER";
  const permissions = userState.kind === "ready" ? userState.data.effective_permissions : [];
  const canManageAppearance =
    permissions.includes("APPEARANCE_SETTINGS_MANAGE") ||
    permissions.includes("APPEARANCE_LOGO_UPLOAD") ||
    permissions.includes("APPEARANCE_LOGO_DELETE") ||
    permissions.includes("APPEARANCE_FAVICON_UPLOAD") ||
    permissions.includes("APPEARANCE_FAVICON_DELETE");
  const canManageGateways =
    permissions.includes("GATEWAYS_VIEW") ||
    permissions.includes("GATEWAYS_UPDATE") ||
    permissions.includes("GATEWAYS_TOGGLE") ||
    permissions.includes("GATEWAYS_REORDER");
  const isGeneralActive = useMatch({ path: "/dashboard/settings", end: true }) !== null;
  const isBotActive = useMatch("/dashboard/settings/bot") !== null;
  const isApiTokensActive = useMatch("/dashboard/settings/api-tokens") !== null;
  const isAppearanceActive = useMatch("/dashboard/settings/appearance") !== null;
  const isGatewaysActive = useMatch("/dashboard/settings/gateways") !== null;

  return (
    <div>
      <nav className="inline-flex gap-1 rounded-full border border-glass-border bg-white/[0.03] p-1 backdrop-blur-md">
        <SettingsTab
          to=""
          end
          icon={SlidersHorizontal}
          label={t("settings.tabs.general")}
          isActive={isGeneralActive}
          bounceStrength={bounceStrength}
        />
        <SettingsTab
          to="bot"
          icon={Bot}
          label={t("settings.tabs.bot")}
          isActive={isBotActive}
          bounceStrength={bounceStrength}
        />
        {isOwner && (
          <SettingsTab
            to="api-tokens"
            icon={KeyRound}
            label={t("settings.tabs.apiTokens")}
            isActive={isApiTokensActive}
            bounceStrength={bounceStrength}
          />
        )}
        {canManageAppearance && (
          <SettingsTab
            to="appearance"
            icon={Palette}
            label={t("settings.tabs.appearance")}
            isActive={isAppearanceActive}
            bounceStrength={bounceStrength}
          />
        )}
        {canManageGateways && (
          <SettingsTab
            to="gateways"
            icon={CreditCard}
            label={t("settings.tabs.gateways")}
            isActive={isGatewaysActive}
            bounceStrength={bounceStrength}
          />
        )}
      </nav>

      <div className="mt-6">
        <Outlet />
      </div>
    </div>
  );
}
