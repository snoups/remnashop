import { ArrowRightLeft, BarChart3, Gift, RefreshCw, Share2, TicketPercent, TrendingUp, Wallet } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { matchPath, Navigate, Outlet, useLocation } from "react-router-dom";

import { usePermissions } from "@entities/user/use-current-user";
import { ANALYTICS_TAB_PERMISSIONS } from "@entities/analytics/api";
import type { AnalyticsPeriod } from "@entities/analytics/api";
import { TabBar } from "@shared/ui/TabBar";
import type { TabBarItem } from "@shared/ui/TabBar";
import type { AnalyticsOutletContext } from "@pages/analytics/period";

const BASE_PATH = "/dashboard/analytics";

const TABS: { key: keyof typeof ANALYTICS_TAB_PERMISSIONS; to: string; icon: TabBarItem["icon"] }[] = [
  { key: "metrics", to: "", icon: BarChart3 },
  { key: "revenue", to: "revenue", icon: Wallet },
  { key: "funnel", to: "funnel", icon: ArrowRightLeft },
  { key: "trial", to: "trial", icon: Gift },
  { key: "retention", to: "retention", icon: RefreshCw },
  { key: "ltv", to: "ltv", icon: TrendingUp },
  { key: "sources", to: "sources", icon: Share2 },
  { key: "promocodes", to: "promocodes", icon: TicketPercent },
];

export function AnalyticsPage() {
  const { t } = useTranslation();
  const { pathname } = useLocation();
  const permissions = usePermissions();
  const [period, setPeriod] = useState<AnalyticsPeriod>({ kind: "days", days: 30 });

  const isActive = (tab: (typeof TABS)[number]) =>
    matchPath({ path: tab.to ? `${BASE_PATH}/${tab.to}` : BASE_PATH, end: tab.to === "" }, pathname) !== null;
  const allowed = (tab: (typeof TABS)[number]) => permissions.includes(ANALYTICS_TAB_PERMISSIONS[tab.key]);

  const items: TabBarItem[] = TABS.filter(allowed).map((tab) => ({
    key: tab.key,
    to: tab.to,
    icon: tab.icon,
    label: t(`analytics.tabs.${tab.key}`),
    isActive: isActive(tab),
  }));

  const activeTab = TABS.find(isActive);
  if (activeTab && !allowed(activeTab)) {
    // the bare /analytics, which the sidebar links to, lands on the first tab allowed
    const firstAllowed = activeTab.to === "" ? items[0] : undefined;
    return <Navigate to={firstAllowed ? `${BASE_PATH}/${firstAllowed.to}` : "/dashboard"} replace />;
  }

  return (
    <div>
      <TabBar items={items} />
      <div className="mt-6">
        <Outlet context={{ period, setPeriod } satisfies AnalyticsOutletContext} />
      </div>
    </div>
  );
}
