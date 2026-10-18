import {
  BadgePercent,
  Ban,
  BarChart3,
  Bot,
  Coins,
  CreditCard,
  Database,
  Globe,
  KeyRound,
  LayoutGrid,
  Layers,
  Link2,
  Megaphone,
  Package,
  Palette,
  ScrollText,
  Settings,
  Share2,
  ShieldCheck,
  SlidersHorizontal,
  Ticket,
  Users,
} from "lucide-react";
import type { ComponentType } from "react";

import { ANALYTICS_TAB_PERMISSIONS } from "@entities/analytics/api";
import type en from "@shared/i18n/locales/en.json";
import type { Permission } from "@shared/types/rbac";

export interface NavItem {
  key: keyof typeof en.sidebar;
  to: string;
  icon: ComponentType<{ className?: string }>;
  end?: boolean;
  /** shown when the actor holds any of these; omitted: always visible (overview, settings) */
  anyOf?: Permission[];
}

export function isNavItemVisible(item: NavItem, permissions: Permission[]): boolean {
  return !item.anyOf || item.anyOf.some((permission) => permissions.includes(permission));
}

export const NAV_ITEMS: NavItem[] = [
  { key: "overview", to: "/dashboard", icon: LayoutGrid, end: true },
  { key: "analytics", to: "/dashboard/analytics", icon: BarChart3, anyOf: Object.values(ANALYTICS_TAB_PERMISSIONS) },
  { key: "users", to: "/dashboard/users", icon: Users, anyOf: ["USERS_VIEW"] },
  { key: "subscriptions", to: "/dashboard/subscriptions", icon: Layers, anyOf: ["SUBSCRIPTIONS_VIEW"] },
  { key: "plans", to: "/dashboard/plans", icon: Package, anyOf: ["PLANS_VIEW"] },
  { key: "promocodes", to: "/dashboard/promocodes", icon: Ticket, anyOf: ["PROMOCODES_VIEW"] },
  { key: "broadcasts", to: "/dashboard/broadcasts", icon: Megaphone, anyOf: ["BROADCASTS_VIEW"] },
  { key: "referrals", to: "/dashboard/referrals", icon: Share2, anyOf: ["REFERRALS_LIST"] },
  { key: "advertising", to: "/dashboard/advertising", icon: Link2, anyOf: ["AD_LINKS_VIEW"] },
  { key: "transactions", to: "/dashboard/transactions", icon: CreditCard, anyOf: ["TRANSACTIONS_VIEW"] },
  { key: "admins", to: "/dashboard/admins", icon: ShieldCheck, anyOf: ["ADMINS_MANAGE"] },
  { key: "eventLog", to: "/dashboard/events", icon: ScrollText, anyOf: ["EVENT_LOG_VIEW"] },
  { key: "settings", to: "/dashboard/settings", icon: Settings },
];

// Settings page tabs; the header search lists the same ones.
export interface SettingsTab {
  key: keyof typeof en.settings.tabs;
  /** relative to /dashboard/settings */
  to: string;
  icon: ComponentType<{ className?: string }>;
  /** shown when the actor holds any of these */
  anyOf: Permission[];
}

export const SETTINGS_TABS: SettingsTab[] = [
  { key: "general", to: "", icon: SlidersHorizontal, anyOf: ["SHOP_SETTINGS_VIEW", "OAUTH_SETTINGS_VIEW", "NOTIFICATION_SETTINGS_VIEW"] },
  { key: "access", to: "access", icon: ShieldCheck, anyOf: ["ACCESS_SETTINGS_VIEW"] },
  {
    key: "bot",
    to: "bot",
    icon: Bot,
    anyOf: ["BOT_SETTINGS_VIEW", "BOT_REQUIREMENTS_VIEW", "BOT_COMMANDS_VIEW", "DIALOGS_CATALOG_VIEW", "TRANSLATIONS_VIEW", "EMOJI_PACKS_VIEW"],
  },
  { key: "cabinet", to: "cabinet", icon: Globe, anyOf: ["CABINET_AUTH_SETTINGS_VIEW", "EMAIL_SETTINGS_VIEW"] },
  { key: "apiTokens", to: "api-tokens", icon: KeyRound, anyOf: ["API_TOKENS_MANAGE"] },
  {
    key: "appearance",
    to: "appearance",
    icon: Palette,
    anyOf: [
      "APPEARANCE_SETTINGS_MANAGE",
      "APPEARANCE_LOGO_UPLOAD",
      "APPEARANCE_LOGO_DELETE",
      "APPEARANCE_FAVICON_UPLOAD",
      "APPEARANCE_FAVICON_DELETE",
    ],
  },
  {
    key: "gateways",
    to: "gateways",
    icon: CreditCard,
    anyOf: ["GATEWAYS_VIEW", "GATEWAYS_UPDATE", "GATEWAYS_ACTIVE_SET", "GATEWAYS_REORDER", "GATEWAYS_TEST"],
  },
  { key: "backups", to: "backups", icon: Database, anyOf: ["BACKUPS_VIEW"] },
  { key: "blacklist", to: "blacklist", icon: Ban, anyOf: ["BLACKLIST_VIEW"] },
  { key: "pricing", to: "pricing", icon: Coins, anyOf: ["PRICING_VIEW"] },
  { key: "referrals", to: "referrals", icon: Share2, anyOf: ["REFERRALS_SETTINGS_VIEW"] },
  { key: "loyalty", to: "loyalty", icon: BadgePercent, anyOf: ["LOYALTY_SETTINGS_VIEW"] },
];
