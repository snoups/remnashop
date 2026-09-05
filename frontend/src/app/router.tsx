import { createBrowserRouter } from "react-router-dom";

import { RequireAuth, RequireGuest } from "@shared/lib/route-guards";
import { DashboardLayout } from "@widgets/dashboard-layout/DashboardLayout";

import {
  AdminsPage,
  AdvertisingPage,
  ApiTokensPage,
  AppearanceSettingsPage,
  BackupsPage,
  BlacklistPage,
  BotSettingsPage,
  DashboardPage,
  EventLogPage,
  GatewaysSettingsPage,
  GeneralSettingsPage,
  LoginPage,
  NotFoundPage,
  OAuthCallbackPage,
  PaymentsPage,
  PlansPage,
  PricingPage,
  ProfilePage,
  PromocodesPage,
  ReferralsPage,
  SettingsPage,
  SubscriptionsPage,
  UsersPage,
} from "./lazy-pages";

export const router = createBrowserRouter([
  {
    path: "/",
    element: (
      <RequireGuest>
        <LoginPage />
      </RequireGuest>
    ),
  },
  {
    path: "/oauth2/callback/:provider",
    element: <OAuthCallbackPage />,
  },
  {
    path: "/dashboard",
    element: (
      <RequireAuth>
        <DashboardLayout />
      </RequireAuth>
    ),
    children: [
      { index: true, element: <DashboardPage /> },
      {
        path: "settings",
        element: <SettingsPage />,
        children: [
          { index: true, element: <GeneralSettingsPage /> },
          { path: "bot", element: <BotSettingsPage /> },
          { path: "api-tokens", element: <ApiTokensPage /> },
          { path: "appearance", element: <AppearanceSettingsPage /> },
          { path: "gateways", element: <GatewaysSettingsPage /> },
          { path: "backups", element: <BackupsPage /> },
          { path: "blacklist", element: <BlacklistPage /> },
          { path: "pricing", element: <PricingPage /> },
        ],
      },
      { path: "profile", element: <ProfilePage /> },
      { path: "admins", element: <AdminsPage /> },
      { path: "users", element: <UsersPage /> },
      { path: "subscriptions", element: <SubscriptionsPage /> },
      { path: "payments", element: <PaymentsPage /> },
      { path: "plans", element: <PlansPage /> },
      { path: "promocodes", element: <PromocodesPage /> },
      { path: "referrals", element: <ReferralsPage /> },
      { path: "advertising", element: <AdvertisingPage /> },
      { path: "event-log", element: <EventLogPage /> },
    ],
  },
  { path: "*", element: <NotFoundPage /> },
]);
