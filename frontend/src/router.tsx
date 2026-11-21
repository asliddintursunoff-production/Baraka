import { lazy, Suspense, type ReactNode } from "react";
import { createBrowserRouter } from "react-router-dom";

import { RequireAuth } from "./lib/auth";
import LoginPage from "./pages/Login";
import MainPage from "./pages/Main";
import Placeholder from "./pages/Placeholder";

// Route-level code splitting (spec §6): heavy pages and voice code load on demand.
const ForecastPage = lazy(() => import("./pages/Forecast"));
const CalendarPage = lazy(() => import("./pages/Calendar"));
const ChatPage = lazy(() => import("./pages/Chat"));
const SourcesPage = lazy(() => import("./pages/Sources"));
const ConnectPage = lazy(() => import("./pages/Connect"));
const DevVoice = lazy(() => import("./pages/dev/DevVoice"));
const LivePage = lazy(() => import("./pages/Live"));

function Lazy({ children }: { children: ReactNode }) {
  return <Suspense fallback={<div className="p-9 text-text-3">Yuklanmoqda…</div>}>{children}</Suspense>;
}

const authed = (node: ReactNode) => (
  <RequireAuth>
    <Lazy>{node}</Lazy>
  </RequireAuth>
);

export const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  { path: "/", element: authed(<MainPage />) },
  { path: "/forecast", element: authed(<ForecastPage />) },
  { path: "/calendar", element: authed(<CalendarPage />) },
  { path: "/chat", element: authed(<ChatPage />) },
  { path: "/knowledge", element: authed(<Placeholder active="knowledge" title="AI bilimi" />) },
  { path: "/sources", element: authed(<SourcesPage />) },
  { path: "/onboarding/connect", element: authed(<ConnectPage />) },
  { path: "/live", element: authed(<LivePage />) },
  { path: "/dev/voice", element: <Lazy><DevVoice /></Lazy> },
  { path: "*", element: authed(<Placeholder active="main" title="Sahifa topilmadi" />) },
]);
