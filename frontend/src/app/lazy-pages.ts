import { lazy } from "react";

export const AdminsPage = lazy(() => import("@pages/admins/AdminsPage").then((m) => ({ default: m.AdminsPage })));
export const AdvertisingPage = lazy(() =>
  import("@pages/advertising/AdvertisingPage").then((m) => ({ default: m.AdvertisingPage })),
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
export const DialogsPage = lazy(() =>
  import("@pages/dialogs/DialogsPage").then((m) => ({ default: m.DialogsPage })),
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
export const SettingsPage = lazy(() =>
  import("@pages/settings/SettingsPage").then((m) => ({ default: m.SettingsPage })),
);
export const SubscriptionsPage = lazy(() =>
  import("@pages/subscriptions/SubscriptionsPage").then((m) => ({ default: m.SubscriptionsPage })),
);
export const UsersPage = lazy(() => import("@pages/users/UsersPage").then((m) => ({ default: m.UsersPage })));
