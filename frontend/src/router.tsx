import { lazy, Suspense, type ReactNode } from "react";
import { createBrowserRouter } from "react-router-dom";

import { HomePlaceholder } from "./pages/HomePlaceholder";

// Route-level code splitting: voice code (and @google/genai) loads only on its page.
const DevVoice = lazy(() => import("./pages/dev/DevVoice"));

function Lazy({ children }: { children: ReactNode }) {
  return <Suspense fallback={<div className="p-9 text-text-3">Yuklanmoqda…</div>}>{children}</Suspense>;
}

export const router = createBrowserRouter([
  { path: "/", element: <HomePlaceholder /> },
  {
    path: "/dev/voice",
    element: (
      <Lazy>
        <DevVoice />
      </Lazy>
    ),
  },
]);
