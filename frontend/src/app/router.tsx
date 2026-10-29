import { createBrowserRouter, Navigate } from "react-router-dom";

import { RequireAuth, RequireGuest } from "@shared/lib/route-guards";
import { DashboardLayout } from "@widgets/dashboard-layout/DashboardLayout";
import { AppRouteError, PageRouteError } from "@widgets/route-error/RouteError";

import {
  AdminsPage,
  AdvertisingPage,
  AnalyticsFunnelPage,
  AnalyticsLtvPage,
  AnalyticsPromocodesPage,
  AnalyticsSourcesPage,
  AnalyticsRetentionPage,
  AnalyticsRevenuePage,
  AnalyticsMetricsPage,
  AnalyticsTrialPage,
  AnalyticsPage,
  ApiTokensPage,
  AppearanceSettingsPage,
  BackupsPage,
  BlacklistPage,
  BotSettingsPage,
  BroadcastDetailsPage,
  BroadcastEditorPage,
  BroadcastsPage,
  CabinetSettingsPage,
  ConnectGuideSettingsPage,
  DashboardPage,
  EventLogPage,
  DebugKitPage,
  DebugPage,
  DebugVariantsPage,
  GatewaysSettingsPage,
  GeneralSettingsPage,
  LoginPage,
  NotFoundPage,
  OAuthCallbackPage,
  TransactionsPage,
  PlansPage,
  PricingPage,
  ProfilePage,
  PromocodesPage,
  ReferralsListPage,
  RewardsSettingsPage,
  SettingsPage,
  SubscriptionsPage,
  UsersPage,
} from "./lazy-pages";

export const router = createBrowserRouter([
  {
    errorElement: <AppRouteError />,
    children: [
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
          {
            errorElement: <PageRouteError />,
            children: [
              { index: true, element: <DashboardPage /> },
              {
                path: "settings",
                element: <SettingsPage />,
                children: [
                  { index: true, element: <GeneralSettingsPage /> },
                  { path: "bot", element: <BotSettingsPage /> },
                  { path: "cabinet", element: <CabinetSettingsPage /> },
                  { path: "connect", element: <ConnectGuideSettingsPage /> },
                  { path: "api-tokens", element: <ApiTokensPage /> },
                  { path: "appearance", element: <AppearanceSettingsPage /> },
                  { path: "gateways", element: <GatewaysSettingsPage /> },
                  { path: "backups", element: <BackupsPage /> },
                  { path: "blacklist", element: <BlacklistPage /> },
                  { path: "pricing", element: <PricingPage /> },
                  { path: "rewards", element: <RewardsSettingsPage /> },
                ],
              },
              { path: "profile", element: <ProfilePage /> },
              { path: "admins", element: <AdminsPage /> },
              { path: "users", element: <UsersPage /> },
              { path: "subscriptions", element: <SubscriptionsPage /> },
              { path: "transactions", element: <TransactionsPage /> },
              { path: "plans", element: <PlansPage /> },
              { path: "promocodes", element: <PromocodesPage /> },
              { path: "broadcasts", element: <BroadcastsPage /> },
              { path: "broadcasts/new", element: <BroadcastEditorPage /> },
              { path: "broadcasts/:id/edit", element: <BroadcastEditorPage /> },
              { path: "broadcasts/:id", element: <BroadcastDetailsPage /> },
              { path: "referrals", element: <ReferralsListPage /> },
              { path: "advertising", element: <AdvertisingPage /> },
              {
                path: "analytics",
                element: <AnalyticsPage />,
                children: [
                  { index: true, element: <AnalyticsMetricsPage /> },
                  { path: "revenue", element: <AnalyticsRevenuePage /> },
                  { path: "funnel", element: <AnalyticsFunnelPage /> },
                  { path: "trial", element: <AnalyticsTrialPage /> },
                  { path: "retention", element: <AnalyticsRetentionPage /> },
                  { path: "cohorts", element: <Navigate to="../retention" replace /> },
                  { path: "ltv", element: <AnalyticsLtvPage /> },
                  { path: "sources", element: <AnalyticsSourcesPage /> },
                  { path: "promocodes", element: <AnalyticsPromocodesPage /> },
                ],
              },
              { path: "events", element: <EventLogPage /> },
              {
                path: "debug",
                element: <DebugPage />,
                children: [
                  { index: true, element: <DebugKitPage /> },
                  { path: "variants", element: <DebugVariantsPage /> },
                ],
              },
            ],
          },
        ],
      },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
]);
