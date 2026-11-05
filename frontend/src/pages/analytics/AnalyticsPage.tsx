import { ArrowRightLeft, BarChart3, Gift, RefreshCw, Share2, TicketPercent, TrendingUp, Wallet } from "lucide-react";
import { useLayoutEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { matchPath, Navigate, Outlet, useLocation } from "react-router-dom";

import { usePermissions } from "@entities/user/use-current-user";
import { ANALYTICS_TAB_PERMISSIONS } from "@entities/analytics/api";
import type { AnalyticsPeriod } from "@entities/analytics/api";
import { LoadGate } from "@shared/lib/load-gate";
import { PAGE_BAR_CLASS, PAGE_CLASS } from "@shared/ui/classes";
import { TabBar, type TabBarItem } from "@shared/ui/glass/TabBar";
import type { AnalyticsOutletContext } from "@pages/analytics/period";
import { PeriodPicker } from "@pages/analytics/PeriodPicker";

const BASE_PATH = "/dashboard/analytics";

const TABS: {
  key: keyof typeof ANALYTICS_TAB_PERMISSIONS;
  to: string;
  icon: TabBarItem["icon"];
  periodIndependent?: boolean;
}[] = [
  { key: "metrics", to: "", icon: BarChart3 },
  { key: "revenue", to: "revenue", icon: Wallet },
  { key: "funnel", to: "funnel", icon: ArrowRightLeft },
  { key: "trial", to: "trial", icon: Gift },
  { key: "retention", to: "retention", icon: RefreshCw, periodIndependent: true },
  { key: "ltv", to: "ltv", icon: TrendingUp, periodIndependent: true },
  { key: "sources", to: "sources", icon: Share2 },
  { key: "promocodes", to: "promocodes", icon: TicketPercent },
];

export function AnalyticsPage() {
  const { t } = useTranslation();
  const { pathname } = useLocation();
  const permissions = usePermissions();
  const [period, setPeriod] = useState<AnalyticsPeriod>({ kind: "days", days: 30 });
  const scrollerRef = useRef<HTMLDivElement>(null);

  // the scroller outlives the tabs; below md it doesn't scroll and main does
  useLayoutEffect(() => {
    scrollerRef.current?.scrollTo(0, 0);
    scrollerRef.current?.closest("main")?.scrollTo(0, 0);
  }, [pathname]);

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
    // as the settings page: the 48px bar floats over a scroller of its own, content starts at 68px
    <div data-fills-main className={PAGE_CLASS}>
      <div className={`${PAGE_BAR_CLASS} flex flex-wrap items-center gap-2 md:flex-nowrap`}>
        <div className="min-w-0">
          <TabBar items={items} />
        </div>
        <div className="ml-auto max-w-full shrink-0">
          {activeTab?.periodIndependent ? (
            <span className="glass-panel flex h-12 items-center rounded-full px-4 text-[13px] font-medium text-muted-foreground">
              {t("analytics.periodIndependent")}
            </span>
          ) : (
            <PeriodPicker period={period} onChange={setPeriod} />
          )}
        </div>
      </div>
      <div
        ref={scrollerRef}
        className="scroll-fade-y scroll-fade-gap page-scroll mt-1 pt-2 md:mt-0 md:min-h-0 md:flex-1 md:overflow-y-auto md:pt-[68px] [--fade-rest-start:48px] [--fade-bottom-size:0px] [scrollbar-gutter:stable] max-md:[scrollbar-gutter:auto] max-md:[scrollbar-width:none] max-md:[&::-webkit-scrollbar]:hidden md:-mr-5 md:pb-5 md:pr-[calc(1.25rem-var(--scrollbar-size))]"
      >
        <LoadGate key={pathname}>
          <Outlet context={{ period, setPeriod } satisfies AnalyticsOutletContext} />
        </LoadGate>
      </div>
    </div>
  );
}
