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
    <div>
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
      <div className="mt-6">
        <Outlet />
      </div>
    </div>
  );
}
