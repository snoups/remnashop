import { Suspense, lazy, useEffect, useState } from "react";
import { RouterProvider } from "react-router-dom";

import { AppearanceProvider } from "@entities/appearance/AppearanceProvider";
import { initializeAuth } from "@shared/api/http";
import { DebugBar } from "@widgets/debug-bar/DebugBar";
import { ToastContainer } from "@widgets/toast/ToastContainer";

import { router } from "./router";

const ShaderBackground = lazy(() =>
  import("./ShaderBackground").then((m) => ({ default: m.ShaderBackground })),
);

export function App() {
  const [authReady, setAuthReady] = useState(false);

  useEffect(() => {
    void initializeAuth().finally(() => setAuthReady(true));
  }, []);

  return (
    <AppearanceProvider>
      <Suspense fallback={null}>
        <ShaderBackground />
      </Suspense>
      {authReady && (
        <Suspense fallback={null}>
          <RouterProvider router={router} />
        </Suspense>
      )}
      <ToastContainer />
      <DebugBar />
    </AppearanceProvider>
  );
}
