import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";

import { getAccessToken } from "./token-storage";

export function RequireGuest({ children }: { children: ReactNode }) {
  return getAccessToken() ? <Navigate to="/dashboard" replace /> : children;
}

export function RequireAuth({ children }: { children: ReactNode }) {
  return getAccessToken() ? children : <Navigate to="/" replace />;
}
