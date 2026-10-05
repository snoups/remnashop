import { useTranslation } from "react-i18next";
import { useLocation } from "react-router-dom";

import { usePermissions } from "@entities/user/use-current-user";
import { TabBar } from "@shared/ui/TabBar";
import { isNavItemVisible, NAV_ITEMS } from "@widgets/sidebar/nav-items";

export function BottomNav() {
  const { t } = useTranslation();
  const { pathname } = useLocation();
  const permissions = usePermissions();
  const items = NAV_ITEMS.filter((item) => isNavItemVisible(item, permissions)).map((item) => ({
    key: item.key,
    to: item.to,
    end: item.end,
    icon: item.icon,
    label: t(`sidebar.${item.key}`),
    isActive: item.end ? pathname === item.to : pathname.startsWith(item.to),
  }));

  return (
    <div className="mx-2 mb-[max(0.5rem,env(safe-area-inset-bottom))] mt-2 flex justify-center md:hidden">
      <TabBar items={items} />
    </div>
  );
}
