import {
  Ban,
  BarChart3,
  Bot,
  Coins,
  CreditCard,
  Database,
  KeyRound,
  LayoutGrid,
  Layers,
  Link2,
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

import type { Permission } from "@shared/types/rbac";

export interface NavItem {
  key: string;
  to: string;
  icon: ComponentType<{ className?: string }>;
  end?: boolean;
  // omitted: always visible (overview, settings)
  permission?: Permission;
}

export const NAV_ITEMS: NavItem[] = [
  { key: "overview", to: "/dashboard", icon: LayoutGrid, end: true },
  { key: "analytics", to: "/dashboard/analytics", icon: BarChart3, permission: "ANALYTICS_VIEW" },
  { key: "users", to: "/dashboard/users", icon: Users, permission: "USERS_VIEW" },
  { key: "subscriptions", to: "/dashboard/subscriptions", icon: Layers, permission: "SUBSCRIPTIONS_VIEW" },
  { key: "plans", to: "/dashboard/plans", icon: Package, permission: "PLANS_VIEW" },
  { key: "promocodes", to: "/dashboard/promocodes", icon: Ticket, permission: "PROMOCODES_VIEW" },
  { key: "referrals", to: "/dashboard/referrals", icon: Share2, permission: "REFERRALS_LIST" },
  { key: "advertising", to: "/dashboard/advertising", icon: Link2, permission: "AD_LINKS_VIEW" },
  { key: "transactions", to: "/dashboard/transactions", icon: CreditCard, permission: "TRANSACTIONS_VIEW" },
  { key: "admins", to: "/dashboard/admins", icon: ShieldCheck, permission: "ADMINS_MANAGE" },
  { key: "eventLog", to: "/dashboard/event-log", icon: ScrollText, permission: "EVENT_LOG_VIEW" },
  { key: "settings", to: "/dashboard/settings", icon: Settings },
];

// Settings page tabs; the header search lists the same ones.
export interface SettingsTab {
  key: string;
  /** relative to /dashboard/settings */
  to: string;
  icon: ComponentType<{ className?: string }>;
  /** shown when the actor holds any of these */
  anyOf: Permission[];
}

export const SETTINGS_TABS: SettingsTab[] = [
  { key: "general", to: "", icon: SlidersHorizontal, anyOf: ["SHOP_SETTINGS_VIEW", "OAUTH_SETTINGS_VIEW"] },
  {
    key: "bot",
    to: "bot",
    icon: Bot,
    anyOf: ["BOT_SETTINGS_VIEW", "BOT_COMMANDS_VIEW", "DIALOGS_CATALOG_VIEW", "TRANSLATIONS_VIEW", "EMOJI_PACKS_VIEW"],
  },
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
];
