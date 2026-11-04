import type { ParseKeys } from "i18next";
import { useTranslation } from "react-i18next";
import { useLocation } from "react-router-dom";

import { useDocumentTitle } from "@shared/lib/use-document-title";

// A page inside a section, matched before the sections; its first group is passed as {{id}}.
const PAGE_TITLE_BY_PATTERN: { pattern: RegExp; key: ParseKeys }[] = [
  { pattern: /^\/dashboard\/broadcasts\/new\/?$/, key: "broadcasts.pageTitle.new" },
  { pattern: /^\/dashboard\/broadcasts\/(\d+)\/edit\/?$/, key: "broadcasts.pageTitle.edit" },
  { pattern: /^\/dashboard\/broadcasts\/(\d+)\/?$/, key: "broadcasts.pageTitle.details" },
];

// Longest-prefix match against location.pathname, most specific first.
const PAGE_TITLE_BY_PATH: { prefix: string; key: ParseKeys }[] = [
  { prefix: "/dashboard/settings", key: "settings.title" },
  { prefix: "/dashboard/profile", key: "profile.title" },
  { prefix: "/dashboard/admins", key: "admins.title" },
  { prefix: "/dashboard/events", key: "eventLog.title" },
  { prefix: "/dashboard/users", key: "users.title" },
  { prefix: "/dashboard/subscriptions", key: "subscriptions.title" },
  { prefix: "/dashboard/transactions", key: "transactions.title" },
  { prefix: "/dashboard/plans", key: "plans.title" },
  { prefix: "/dashboard/promocodes", key: "promocodes.title" },
  { prefix: "/dashboard/broadcasts", key: "sidebar.broadcasts" },
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
  const page = PAGE_TITLE_BY_PATTERN.map(({ pattern, key }) => ({ key, match: pattern.exec(location.pathname) })).find(
    ({ match }) => match,
  );
  const key = PAGE_TITLE_BY_PATH.find(({ prefix }) => location.pathname.startsWith(prefix))?.key ?? "sidebar.overview";
  const title = page ? t(page.key, { id: page.match?.[1] }) : t(key);

  useDocumentTitle(brandName, title);

  return title;
}
