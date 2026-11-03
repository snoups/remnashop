import { MotionConfig } from "motion/react";
import { Component, Suspense, lazy, useEffect, useState, type ReactNode } from "react";
import { RouterProvider } from "react-router-dom";

import { AppearanceProvider } from "@entities/appearance/AppearanceProvider";
import { initializeAuth } from "@shared/api/http";
import { DebugBar } from "@widgets/debug-bar/DebugBar";
import { ToastContainer } from "@widgets/toast/ToastContainer";

import { router } from "./router";

const ShaderBackground = lazy(() =>
  import("./ShaderBackground").then((m) => ({ default: m.ShaderBackground })),
);

// The background is decorative and lives outside the router's error handling:
// if its chunk or WebGL setup throws, render nothing rather than blank the app.
class SilentBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    return this.state.failed ? null : this.props.children;
  }
}

export function App() {
  const [authReady, setAuthReady] = useState(false);

  useEffect(() => {
    void initializeAuth().finally(() => setAuthReady(true));
  }, []);

  return (
    <MotionConfig reducedMotion="user">
    <AppearanceProvider>
      <SilentBoundary>
        <Suspense fallback={null}>
          <ShaderBackground />
        </Suspense>
      </SilentBoundary>
      {authReady && (
        <Suspense fallback={null}>
          <RouterProvider router={router} />
        </Suspense>
      )}
      <ToastContainer />
      <DebugBar />
    </AppearanceProvider>
    </MotionConfig>
  );
}
