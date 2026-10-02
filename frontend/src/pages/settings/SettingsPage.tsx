import {
  Ban,
  Bot,
  Coins,
  CreditCard,
  Database,
  KeyRound,
  Palette,
  Share2,
  SlidersHorizontal,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { Outlet, useMatch } from "react-router-dom";

import { useCurrentUser } from "@entities/user/use-current-user";
import { TabBar } from "@shared/ui/TabBar";
import type { TabBarItem } from "@shared/ui/TabBar";

export function SettingsPage() {
  const { t } = useTranslation();
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
    permissions.includes("GATEWAYS_ACTIVE_SET") ||
    permissions.includes("GATEWAYS_REORDER") ||
    permissions.includes("GATEWAYS_TEST");
  const canManageBackups = permissions.includes("BACKUPS_VIEW");
  const canViewBlacklist = permissions.includes("BLACKLIST_VIEW");
  const canViewPricing = permissions.includes("PRICING_VIEW");
  const canViewReferrals = permissions.includes("REFERRALS_SETTINGS_VIEW");
  const isGeneralActive = useMatch({ path: "/dashboard/settings", end: true }) !== null;
  const isBotActive = useMatch("/dashboard/settings/bot") !== null;
  const isApiTokensActive = useMatch("/dashboard/settings/api-tokens") !== null;
  const isAppearanceActive = useMatch("/dashboard/settings/appearance") !== null;
  const isGatewaysActive = useMatch("/dashboard/settings/gateways") !== null;
  const isBackupsActive = useMatch("/dashboard/settings/backups") !== null;
  const isBlacklistActive = useMatch("/dashboard/settings/blacklist") !== null;
  const isPricingActive = useMatch("/dashboard/settings/pricing") !== null;
  const isReferralsActive = useMatch("/dashboard/settings/referrals") !== null;

  const items: TabBarItem[] = [
    { key: "general", to: "", end: true, icon: SlidersHorizontal, label: t("settings.tabs.general"), isActive: isGeneralActive },
    { key: "bot", to: "bot", icon: Bot, label: t("settings.tabs.bot"), isActive: isBotActive },
    ...(isOwner
      ? [{ key: "apiTokens", to: "api-tokens", icon: KeyRound, label: t("settings.tabs.apiTokens"), isActive: isApiTokensActive }]
      : []),
    ...(canManageAppearance
      ? [{ key: "appearance", to: "appearance", icon: Palette, label: t("settings.tabs.appearance"), isActive: isAppearanceActive }]
      : []),
    ...(canManageGateways
      ? [{ key: "gateways", to: "gateways", icon: CreditCard, label: t("settings.tabs.gateways"), isActive: isGatewaysActive }]
      : []),
    ...(canManageBackups
      ? [{ key: "backups", to: "backups", icon: Database, label: t("settings.tabs.backups"), isActive: isBackupsActive }]
      : []),
    ...(canViewBlacklist
      ? [{ key: "blacklist", to: "blacklist", icon: Ban, label: t("settings.tabs.blacklist"), isActive: isBlacklistActive }]
      : []),
    ...(canViewPricing
      ? [{ key: "pricing", to: "pricing", icon: Coins, label: t("settings.tabs.pricing"), isActive: isPricingActive }]
      : []),
    ...(canViewReferrals
      ? [{ key: "referrals", to: "referrals", icon: Share2, label: t("settings.tabs.referrals"), isActive: isReferralsActive }]
      : []),
  ];

  return (
    <div>
      <TabBar items={items} />
      <div className="mt-6">
        <Outlet />
      </div>
    </div>
  );
}
