import { createBrowserRouter } from "react-router-dom";

import { RequireAuth, RequireGuest } from "@shared/lib/route-guards";
import { DashboardLayout } from "@widgets/dashboard-layout/DashboardLayout";

import {
  AdminsPage,
  ApiTokensPage,
  AppearanceSettingsPage,
  BotSettingsPage,
  DashboardPage,
  EventLogPage,
  GatewaysSettingsPage,
  GeneralSettingsPage,
  LoginPage,
  NotFoundPage,
  OAuthCallbackPage,
  ProfilePage,
  SettingsPage,
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
        ],
      },
      { path: "profile", element: <ProfilePage /> },
      { path: "admins", element: <AdminsPage /> },
      { path: "users", element: <UsersPage /> },
      { path: "event-log", element: <EventLogPage /> },
    ],
  },
  { path: "*", element: <NotFoundPage /> },
]);
