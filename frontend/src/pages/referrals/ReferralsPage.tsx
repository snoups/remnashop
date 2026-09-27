import { SlidersHorizontal, Users } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Outlet, useMatch } from "react-router-dom";

import { useBounceStrength } from "@shared/lib/bounceState";
import { TabBar } from "@shared/ui/TabBar";
import type { TabBarItem } from "@shared/ui/TabBar";

export function ReferralsPage() {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const isListActive = useMatch({ path: "/dashboard/referrals", end: true }) !== null;
  const isSettingsActive = useMatch("/dashboard/referrals/settings") !== null;

  const items: TabBarItem[] = [
    { key: "list", to: "", end: true, icon: Users, label: t("referrals.tabs.list"), isActive: isListActive },
    { key: "settings", to: "settings", icon: SlidersHorizontal, label: t("referrals.tabs.settings"), isActive: isSettingsActive },
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
