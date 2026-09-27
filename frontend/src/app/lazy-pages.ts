import { lazy } from "react";

export const AdminsPage = lazy(() => import("@pages/admins/AdminsPage").then((m) => ({ default: m.AdminsPage })));
export const AdvertisingPage = lazy(() =>
  import("@pages/advertising/AdvertisingPage").then((m) => ({ default: m.AdvertisingPage })),
);
export const AnalyticsCohortsPage = lazy(() =>
  import("@pages/analytics/AnalyticsCohortsPage").then((m) => ({ default: m.AnalyticsCohortsPage })),
);
export const AnalyticsFunnelPage = lazy(() =>
  import("@pages/analytics/AnalyticsFunnelPage").then((m) => ({ default: m.AnalyticsFunnelPage })),
);
export const AnalyticsLtvPage = lazy(() =>
  import("@pages/analytics/AnalyticsLtvPage").then((m) => ({ default: m.AnalyticsLtvPage })),
);
export const AnalyticsOverviewPage = lazy(() =>
  import("@pages/analytics/AnalyticsOverviewPage").then((m) => ({ default: m.AnalyticsOverviewPage })),
);
export const AnalyticsPage = lazy(() =>
  import("@pages/analytics/AnalyticsPage").then((m) => ({ default: m.AnalyticsPage })),
);
export const ApiTokensPage = lazy(() =>
  import("@pages/settings/ApiTokensPage").then((m) => ({ default: m.ApiTokensPage })),
);
export const AppearanceSettingsPage = lazy(() =>
  import("@pages/settings/AppearanceSettingsPage").then((m) => ({ default: m.AppearanceSettingsPage })),
);
export const BackupsPage = lazy(() =>
  import("@pages/backups/BackupsPage").then((m) => ({ default: m.BackupsPage })),
);
export const BlacklistPage = lazy(() =>
  import("@pages/blacklist/BlacklistPage").then((m) => ({ default: m.BlacklistPage })),
);
export const BotSettingsPage = lazy(() =>
  import("@pages/settings/BotSettingsPage").then((m) => ({ default: m.BotSettingsPage })),
);
export const DashboardPage = lazy(() =>
  import("@pages/dashboard/DashboardPage").then((m) => ({ default: m.DashboardPage })),
);
export const EventLogPage = lazy(() =>
  import("@pages/event-log/EventLogPage").then((m) => ({ default: m.EventLogPage })),
);
export const GatewaysSettingsPage = lazy(() =>
  import("@pages/settings/GatewaysSettingsPage").then((m) => ({ default: m.GatewaysSettingsPage })),
);
export const GeneralSettingsPage = lazy(() =>
  import("@pages/settings/GeneralSettingsPage").then((m) => ({ default: m.GeneralSettingsPage })),
);
export const LoginPage = lazy(() => import("@pages/auth/LoginPage").then((m) => ({ default: m.LoginPage })));
export const NotFoundPage = lazy(() =>
  import("@pages/not-found/NotFoundPage").then((m) => ({ default: m.NotFoundPage })),
);
export const OAuthCallbackPage = lazy(() =>
  import("@pages/auth/OAuthCallbackPage").then((m) => ({ default: m.OAuthCallbackPage })),
);
export const PaymentsPage = lazy(() =>
  import("@pages/payments/PaymentsPage").then((m) => ({ default: m.PaymentsPage })),
);
export const PlansPage = lazy(() => import("@pages/plans/PlansPage").then((m) => ({ default: m.PlansPage })));
export const PricingPage = lazy(() => import("@pages/pricing/PricingPage").then((m) => ({ default: m.PricingPage })));
export const ProfilePage = lazy(() => import("@pages/profile/ProfilePage").then((m) => ({ default: m.ProfilePage })));
export const PromocodesPage = lazy(() =>
  import("@pages/promocodes/PromocodesPage").then((m) => ({ default: m.PromocodesPage })),
);
export const ReferralsPage = lazy(() =>
  import("@pages/referrals/ReferralsPage").then((m) => ({ default: m.ReferralsPage })),
);
export const ReferralsListPage = lazy(() =>
  import("@pages/referrals/ReferralsListPage").then((m) => ({ default: m.ReferralsListPage })),
);
export const ReferralSettingsPage = lazy(() =>
  import("@pages/referrals/ReferralSettingsPage").then((m) => ({ default: m.ReferralSettingsPage })),
);
export const SettingsPage = lazy(() =>
  import("@pages/settings/SettingsPage").then((m) => ({ default: m.SettingsPage })),
);
export const SubscriptionsPage = lazy(() =>
  import("@pages/subscriptions/SubscriptionsPage").then((m) => ({ default: m.SubscriptionsPage })),
);
export const UsersPage = lazy(() => import("@pages/users/UsersPage").then((m) => ({ default: m.UsersPage })));
