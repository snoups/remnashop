import { BarChart3, CreditCard, LayoutGrid, Layers, Link2, Package, ScrollText, Settings, Share2, ShieldCheck, Ticket, Users } from "lucide-react";
import type { ComponentType } from "react";

import type { Permission } from "@shared/types/rbac";

export interface NavItem {
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

export const NAV_ITEMS: NavItem[] = [
  { key: "overview", to: "/dashboard", icon: LayoutGrid, end: true },
  { key: "analytics", to: "/dashboard/analytics", icon: BarChart3, permission: "ANALYTICS_VIEW" },
  { key: "users", to: "/dashboard/users", icon: Users, permission: "USERS_VIEW" },
  { key: "subscriptions", to: "/dashboard/subscriptions", icon: Layers, permission: "SUBSCRIPTIONS_VIEW" },
  { key: "plans", to: "/dashboard/plans", icon: Package, permission: "PLANS_VIEW" },
  { key: "promocodes", to: "/dashboard/promocodes", icon: Ticket, permission: "PROMOCODES_VIEW" },
  { key: "referrals", to: "/dashboard/referrals", icon: Share2, permission: "REFERRALS_LIST" },
  { key: "advertising", to: "/dashboard/advertising", icon: Link2, permission: "AD_LINKS_VIEW" },
  { key: "payments", to: "/dashboard/payments", icon: CreditCard, permission: "PAYMENTS_VIEW" },
  { key: "admins", to: "/dashboard/admins", icon: ShieldCheck, permission: "ADMINS_MANAGE" },
  { key: "eventLog", to: "/dashboard/event-log", icon: ScrollText, permission: "EVENT_LOG_VIEW" },
  { key: "settings", to: "/dashboard/settings", icon: Settings },
];
