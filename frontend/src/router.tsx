import { lazy, Suspense, type ReactNode } from "react";
import { createBrowserRouter, type RouteObject } from "react-router-dom";

import { PublicOnly, RequireAuth } from "./lib/auth";
import LandingPage from "./pages/Landing";
import LoginPage from "./pages/Login";
import MainPage from "./pages/Main";
import Placeholder from "./pages/Placeholder";
import RegisterPage from "./pages/Register";
import { RouteError } from "@/components/ErrorFallbacks";

// Route-level code splitting (spec §6): heavy pages and voice code load on demand.
const ForecastPage = lazy(() => import("./pages/Forecast"));
const CalendarPage = lazy(() => import("./pages/Calendar"));
const ChatPage = lazy(() => import("./pages/Chat"));
const SourcesPage = lazy(() => import("./pages/Sources"));
const ConnectPage = lazy(() => import("./pages/Connect"));
const DevVoice = lazy(() => import("./pages/dev/DevVoice"));
const LivePage = lazy(() => import("./pages/Live"));
const KnowledgePage = lazy(() => import("./pages/Knowledge"));
const PricingPage = lazy(() => import("./pages/Pricing"));
const OnboardingPage = lazy(() => import("./pages/Onboarding"));
const FirstSyncPage = lazy(() => import("./pages/FirstSync"));
const FilesPage = lazy(() => import("./pages/Files"));

function Lazy({ children }: { children: ReactNode }) {
  return <Suspense fallback={<div className="p-9 text-text-3">Yuklanmoqda…</div>}>{children}</Suspense>;
}

const authed = (node: ReactNode) => (
  <RequireAuth>
    <Lazy>{node}</Lazy>
  </RequireAuth>
);

/** Onboarding routes: login required, but allowed before onboarding is done. */
const onboarding = (node: ReactNode) => (
  <RequireAuth onboarding>
    <Lazy>{node}</Lazy>
  </RequireAuth>
);

const publicOnly = (node: ReactNode) => <PublicOnly>{node}</PublicOnly>;

const ROUTES: RouteObject[] = [
  { path: "/", element: publicOnly(<LandingPage />) },
  { path: "/login", element: publicOnly(<LoginPage />) },
  { path: "/register", element: publicOnly(<RegisterPage />) },
  { path: "/pricing", element: <Lazy><PricingPage /></Lazy> },
  { path: "/dashboard", element: authed(<MainPage />) },
  { path: "/forecast", element: authed(<ForecastPage />) },
  { path: "/calendar", element: authed(<CalendarPage />) },
  { path: "/chat", element: authed(<ChatPage />) },
  { path: "/knowledge", element: authed(<KnowledgePage />) },
  { path: "/sources", element: authed(<SourcesPage />) },
  { path: "/files", element: authed(<FilesPage />) },
  { path: "/onboarding/business", element: onboarding(<OnboardingPage />) },
  { path: "/onboarding/connect", element: onboarding(<ConnectPage />) },
  { path: "/onboarding/analyzing", element: onboarding(<FirstSyncPage />) },
  { path: "/live", element: authed(<LivePage />) },
  { path: "/dev/voice", element: <Lazy><DevVoice /></Lazy> },
  { path: "*", element: authed(<Placeholder active="main" title="Sahifa topilmadi" />) },
];

// every route: a friendly Uzbek error page instead of the developer one
export const router = createBrowserRouter(ROUTES.map((r) => ({ ...r, errorElement: <RouteError /> })));
