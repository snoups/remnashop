import { useTranslation } from "react-i18next";
import { matchPath, Navigate, Outlet, useLocation } from "react-router-dom";

import { usePermissions } from "@entities/user/use-current-user";
import { TabBar } from "@shared/ui/glass/TabBar";
import { SETTINGS_TABS, type SettingsTab } from "@widgets/sidebar/nav-items";

const SETTINGS_ROOT = "/dashboard/settings";

export function SettingsPage() {
  const { t } = useTranslation();
  const { pathname } = useLocation();
  const permissions = usePermissions();

  const tabs = SETTINGS_TABS.filter((tab) => tab.anyOf.some((permission) => permissions.includes(permission)));
  const isActive = (tab: SettingsTab) =>
    matchPath({ path: `${SETTINGS_ROOT}/${tab.to}`, end: tab.to === "" }, pathname) !== null;


  // a hidden tab is off limits by URL too; the bare /settings lands on the first one allowed.
  // Only while the URL is still under settings: leaving, this page stays mounted through the
  // outlet's fade-out with the next page's URL already in place.
  const isUnderSettings = matchPath({ path: SETTINGS_ROOT, end: false }, pathname) !== null;
  if (isUnderSettings && !tabs.some(isActive)) {
    return <Navigate to={tabs.length > 0 ? `${SETTINGS_ROOT}/${tabs[0].to}` : "/dashboard"} replace />;
  }

  return (
    // fills main and scrolls on its own (data-fills-main: see AnimatedOutlet and main). Negative
    // margins hand main's bottom and right padding to the scroller, so its scrollbar sits on the
    // panel edge as main's did; pr-[var(--scrollbar-size)] is the scrollbar; no bottom fade. Desktop: the 48px tab bar floats
    // over the scroller's top. Under it a 20px gap, as between cards: content scrolling up is gone
    // under the bar and the gap's first 8px (0–56px), fades in over the last 12px (56–68px), and
    // starts at 68px at rest; scroll-pt lands a linked card (#access) there too
    <div data-fills-main className="relative flex flex-1 flex-col md:min-h-0 md:pr-[var(--scrollbar-size)] md:-mb-5">
      <div className="md:absolute md:left-0 md:right-[var(--scrollbar-size)] md:top-0 md:z-10">
        <TabBar
          items={tabs.map((tab) => ({
            key: tab.key,
            to: tab.to,
            icon: tab.icon,
            label: t(`settings.tabs.${tab.key}`),
            isActive: isActive(tab),
          }))}
        />
      </div>
      <div
        className="scroll-fade-y page-scroll mt-1 pt-2 md:mt-0 md:min-h-0 md:flex-1 md:overflow-y-auto md:pt-[68px] md:scroll-pt-[68px] [--fade-top-size:12px] [--fade-top-start:56px] [--fade-bottom-size:0px] [scrollbar-gutter:stable] max-md:[scrollbar-gutter:auto] max-md:[scrollbar-width:none] max-md:[&::-webkit-scrollbar]:hidden md:-mr-5 md:pb-5 md:pr-[calc(1.25rem-var(--scrollbar-size))]"
      >
        <Outlet />
      </div>
    </div>
  );
}
