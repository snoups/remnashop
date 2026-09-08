import { ArrowRightLeft, BarChart3, Layers, TrendingUp } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Outlet, useMatch } from "react-router-dom";

import { useBounceStrength } from "@shared/lib/bounceState";
import { TabBar } from "@shared/ui/TabBar";
import type { TabBarItem } from "@shared/ui/TabBar";

export function AnalyticsPage() {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const isOverviewActive = useMatch({ path: "/dashboard/analytics", end: true }) !== null;
  const isFunnelActive = useMatch("/dashboard/analytics/funnel") !== null;
  const isCohortsActive = useMatch("/dashboard/analytics/cohorts") !== null;
  const isLtvActive = useMatch("/dashboard/analytics/ltv") !== null;

  const items: TabBarItem[] = [
    { key: "overview", to: "", end: true, icon: BarChart3, label: t("analytics.tabs.overview"), isActive: isOverviewActive },
    { key: "funnel", to: "funnel", icon: ArrowRightLeft, label: t("analytics.tabs.funnel"), isActive: isFunnelActive },
    { key: "cohorts", to: "cohorts", icon: Layers, label: t("analytics.tabs.cohorts"), isActive: isCohortsActive },
    { key: "ltv", to: "ltv", icon: TrendingUp, label: t("analytics.tabs.ltv"), isActive: isLtvActive },
  ];

  return (
    <div>
      <TabBar items={items} bounceStrength={bounceStrength} />
      <div className="mt-6">
        <Outlet />
      </div>
    </div>
  );
}
