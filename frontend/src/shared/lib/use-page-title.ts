import { useTranslation } from "react-i18next";
import { useLocation } from "react-router-dom";

import { useDocumentTitle } from "@shared/lib/use-document-title";

// Longest-prefix match against location.pathname, most specific first.
const PAGE_TITLE_BY_PATH: { prefix: string; key: string }[] = [
  { prefix: "/dashboard/settings", key: "settings.title" },
  { prefix: "/dashboard/profile", key: "profile.title" },
  { prefix: "/dashboard/admins", key: "admins.title" },
  { prefix: "/dashboard/event-log", key: "eventLog.title" },
  { prefix: "/dashboard/users", key: "users.title" },
  { prefix: "/dashboard/subscriptions", key: "subscriptions.title" },
  { prefix: "/dashboard/payments", key: "payments.title" },
  { prefix: "/dashboard/plans", key: "plans.title" },
  { prefix: "/dashboard/promocodes", key: "promocodes.title" },
  { prefix: "/dashboard/referrals", key: "referrals.title" },
  { prefix: "/dashboard/advertising", key: "advertising.title" },
  { prefix: "/dashboard/analytics", key: "analytics.title" },
  { prefix: "/dashboard/debug", key: "debugPage.title" },
  { prefix: "/dashboard", key: "sidebar.overview" },
];

/** Resolves the current /dashboard/* route to its title and sets document.title to match. */
export function usePageTitle(brandName: string): string {
  const { t } = useTranslation();
  const location = useLocation();
  const key = PAGE_TITLE_BY_PATH.find(({ prefix }) => location.pathname.startsWith(prefix))?.key ?? "sidebar.overview";
  const title = t(key);

  useDocumentTitle(brandName, title);

  return title;
}
