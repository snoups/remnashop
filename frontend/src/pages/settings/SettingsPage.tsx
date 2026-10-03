import { useTranslation } from "react-i18next";
import { matchPath, Navigate, Outlet, useLocation } from "react-router-dom";

import { usePermissions } from "@entities/user/use-current-user";
import { TabBar } from "@shared/ui/TabBar";
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
    // fills main and scrolls on its own, so the tabs stay put like a dialog's (data-fills-main:
    // see AnimatedOutlet and main). Negative margins hand main's bottom and right padding to the
    // scroller, so its scrollbar sits on the panel edge as main's did; pr-2.5 is that 10px
    // scrollbar, keeping the tabs as wide as before. The 12px under the tabs is 4px outside the
    // scroller and 8px of padding under its 8px fade, so content stays 12px off the tabs both at
    // rest and while scrolling
    <div data-fills-main className="-mb-6 flex min-h-0 flex-1 flex-col pr-2.5 md:-mb-8">
      <TabBar
        items={tabs.map((tab) => ({
          key: tab.key,
          to: tab.to,
          end: tab.to === "",
          icon: tab.icon,
          label: t(`settings.tabs.${tab.key}`),
          isActive: isActive(tab),
        }))}
      />
      <div className="scroll-fade-y -mr-4 mt-1 min-h-0 flex-1 overflow-y-auto pt-2 [--fade-top-size:8px] [scrollbar-gutter:stable] pb-6 pr-[calc(1rem-10px)] md:-mr-8 md:pb-8 md:pr-[calc(2rem-10px)]">
        <Outlet />
      </div>
    </div>
  );
}
