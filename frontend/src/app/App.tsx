import { Suspense, lazy, useEffect, useState } from "react";
import { RouterProvider } from "react-router-dom";

import { AppearanceProvider } from "@entities/appearance/AppearanceProvider";
import { initializeAuth } from "@shared/api/http";
import { ToastContainer } from "@widgets/toast/ToastContainer";

import { router } from "./router";

const ShaderBackground = lazy(() =>
  import("./ShaderBackground").then((m) => ({ default: m.ShaderBackground })),
);

// import.meta.env.DEV is statically replaced with `false` in production builds,
// so this whole branch (DebugPanel, leva) is dead code and gets tree-shaken out.
const DebugPanel = import.meta.env.DEV
  ? lazy(() => import("./DebugPanel").then((m) => ({ default: m.DebugPanel })))
  : null;

export function App() {
  const [authReady, setAuthReady] = useState(false);

  useEffect(() => {
    void initializeAuth().finally(() => setAuthReady(true));
  }, []);

  return (
    <AppearanceProvider>
      <Suspense fallback={null}>
        <ShaderBackground />
        {DebugPanel && <DebugPanel />}
      </Suspense>
      {authReady && (
        <Suspense fallback={null}>
          <RouterProvider router={router} />
        </Suspense>
      )}
      <ToastContainer />
    </AppearanceProvider>
  );
}
