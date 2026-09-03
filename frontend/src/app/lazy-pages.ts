import { lazy } from "react";

export const AdminsPage = lazy(() => import("@pages/admins/AdminsPage").then((m) => ({ default: m.AdminsPage })));
export const BlacklistPage = lazy(() =>
  import("@pages/blacklist/BlacklistPage").then((m) => ({ default: m.BlacklistPage })),
);
export const LoginPage = lazy(() => import("@pages/auth/LoginPage").then((m) => ({ default: m.LoginPage })));
export const OAuthCallbackPage = lazy(() =>
  import("@pages/auth/OAuthCallbackPage").then((m) => ({ default: m.OAuthCallbackPage })),
);
export const DashboardPage = lazy(() =>
  import("@pages/dashboard/DashboardPage").then((m) => ({ default: m.DashboardPage })),
);
export const EventLogPage = lazy(() =>
  import("@pages/event-log/EventLogPage").then((m) => ({ default: m.EventLogPage })),
);
export const NotFoundPage = lazy(() =>
  import("@pages/not-found/NotFoundPage").then((m) => ({ default: m.NotFoundPage })),
);
export const PricingPage = lazy(() => import("@pages/pricing/PricingPage").then((m) => ({ default: m.PricingPage })));
export const ProfilePage = lazy(() => import("@pages/profile/ProfilePage").then((m) => ({ default: m.ProfilePage })));
export const ApiTokensPage = lazy(() =>
  import("@pages/settings/ApiTokensPage").then((m) => ({ default: m.ApiTokensPage })),
);
export const AppearanceSettingsPage = lazy(() =>
  import("@pages/settings/AppearanceSettingsPage").then((m) => ({ default: m.AppearanceSettingsPage })),
);
export const BotSettingsPage = lazy(() =>
  import("@pages/settings/BotSettingsPage").then((m) => ({ default: m.BotSettingsPage })),
);
export const GatewaysSettingsPage = lazy(() =>
  import("@pages/settings/GatewaysSettingsPage").then((m) => ({ default: m.GatewaysSettingsPage })),
);
export const GeneralSettingsPage = lazy(() =>
  import("@pages/settings/GeneralSettingsPage").then((m) => ({ default: m.GeneralSettingsPage })),
);
export const SettingsPage = lazy(() =>
  import("@pages/settings/SettingsPage").then((m) => ({ default: m.SettingsPage })),
);
export const UsersPage = lazy(() => import("@pages/users/UsersPage").then((m) => ({ default: m.UsersPage })));
