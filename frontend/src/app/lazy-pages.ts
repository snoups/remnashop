import { lazy } from "react";

export const AdminsPage = lazy(() => import("@pages/admins/AdminsPage").then((m) => ({ default: m.AdminsPage })));
export const AdvertisingPage = lazy(() =>
  import("@pages/advertising/AdvertisingPage").then((m) => ({ default: m.AdvertisingPage })),
);
export const AnalyticsFunnelPage = lazy(() =>
  import("@pages/analytics/AnalyticsFunnelPage").then((m) => ({ default: m.AnalyticsFunnelPage })),
);
export const AnalyticsLtvPage = lazy(() =>
  import("@pages/analytics/AnalyticsLtvPage").then((m) => ({ default: m.AnalyticsLtvPage })),
);
export const AnalyticsMetricsPage = lazy(() =>
  import("@pages/analytics/AnalyticsMetricsPage").then((m) => ({ default: m.AnalyticsMetricsPage })),
);
export const AnalyticsPromocodesPage = lazy(() =>
  import("@pages/analytics/AnalyticsPromocodesPage").then((m) => ({ default: m.AnalyticsPromocodesPage })),
);
export const AnalyticsSourcesPage = lazy(() =>
  import("@pages/analytics/AnalyticsSourcesPage").then((m) => ({ default: m.AnalyticsSourcesPage })),
);
export const AnalyticsRevenuePage = lazy(() =>
  import("@pages/analytics/AnalyticsRevenuePage").then((m) => ({ default: m.AnalyticsRevenuePage })),
);
export const AnalyticsRetentionPage = lazy(() =>
  import("@pages/analytics/AnalyticsRetentionPage").then((m) => ({ default: m.AnalyticsRetentionPage })),
);
export const AnalyticsTrialPage = lazy(() =>
  import("@pages/analytics/AnalyticsTrialPage").then((m) => ({ default: m.AnalyticsTrialPage })),
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
export const BroadcastsPage = lazy(() =>
  import("@pages/broadcasts/BroadcastsPage").then((m) => ({ default: m.BroadcastsPage })),
);
export const BroadcastDetailsPage = lazy(() =>
  import("@pages/broadcasts/BroadcastDetailsPage").then((m) => ({ default: m.BroadcastDetailsPage })),
);
export const BroadcastEditorPage = lazy(() =>
  import("@pages/broadcasts/BroadcastEditorPage").then((m) => ({ default: m.BroadcastEditorPage })),
);
export const BotSettingsPage = lazy(() =>
  import("@pages/settings/BotSettingsPage").then((m) => ({ default: m.BotSettingsPage })),
);
export const CabinetSettingsPage = lazy(() =>
  import("@pages/settings/CabinetSettingsPage").then((m) => ({ default: m.CabinetSettingsPage })),
);
export const ConnectGuideSettingsPage = lazy(() =>
  import("@pages/settings/ConnectGuideSettingsPage").then((m) => ({ default: m.ConnectGuideSettingsPage })),
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
export const TransactionsPage = lazy(() =>
  import("@pages/transactions/TransactionsPage").then((m) => ({ default: m.TransactionsPage })),
);
export const PlansPage = lazy(() => import("@pages/plans/PlansPage").then((m) => ({ default: m.PlansPage })));
export const PricingPage = lazy(() => import("@pages/pricing/PricingPage").then((m) => ({ default: m.PricingPage })));
export const ProfilePage = lazy(() => import("@pages/profile/ProfilePage").then((m) => ({ default: m.ProfilePage })));
export const PromocodesPage = lazy(() =>
  import("@pages/promocodes/PromocodesPage").then((m) => ({ default: m.PromocodesPage })),
);
export const ReferralsListPage = lazy(() =>
  import("@pages/referrals/ReferralsListPage").then((m) => ({ default: m.ReferralsListPage })),
);
export const RewardsSettingsPage = lazy(() =>
  import("@pages/settings/RewardsSettingsPage").then((m) => ({ default: m.RewardsSettingsPage })),
);
export const SettingsPage = lazy(() =>
  import("@pages/settings/SettingsPage").then((m) => ({ default: m.SettingsPage })),
);
export const SubscriptionsPage = lazy(() =>
  import("@pages/subscriptions/SubscriptionsPage").then((m) => ({ default: m.SubscriptionsPage })),
);
export const UsersPage = lazy(() => import("@pages/users/UsersPage").then((m) => ({ default: m.UsersPage })));
export const DebugPage = lazy(() =>
  import("@pages/debug/DebugPage").then((m) => ({ default: m.DebugPage })),
);
export const DebugKitPage = lazy(() =>
  import("@pages/debug/DebugPage").then((m) => ({ default: m.DebugKitPage })),
);
export const DebugVariantsPage = lazy(() =>
  import("@pages/debug/DebugVariantsPage").then((m) => ({ default: m.DebugVariantsPage })),
);
