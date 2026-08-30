import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "@app/App";
import "@shared/i18n";

import "@app/styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
