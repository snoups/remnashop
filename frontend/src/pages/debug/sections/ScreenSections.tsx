import { X } from "lucide-react";
import { useState, type ReactNode } from "react";

import { OAuthCallbackScreen } from "@pages/auth/OAuthCallbackPage";
import { NotFoundPage } from "@pages/not-found/NotFoundPage";
import { DebugSection, Specimen } from "@pages/debug/debug-ui";
import { useKit } from "@pages/debug/use-kit";
import { Button } from "@shared/ui/Button";
import { IconButton } from "@shared/ui/IconButton";
import { AppRouteError, PageRouteError } from "@widgets/route-error/RouteError";
import { ServerError, ServerUnreachable } from "@widgets/server-error/ServerError";

const SCREENS = {
  crash: AppRouteError,
  notFound: NotFoundPage,
  serverError: ServerError,
  serverUnreachable: ServerUnreachable,
  oauthCallback: OAuthCallbackScreen,
} as const;

type ScreenKey = keyof typeof SCREENS;

// a screen over the whole window, as it shows; the cross in the corner closes it
function ScreenOverlay({ onClose, children }: { onClose: () => void; children: ReactNode }) {
  return (
    <div className="fixed inset-0 z-[100] overflow-y-auto bg-canvas">
      <div className="absolute left-4 top-4 z-10">
        <IconButton size="9" onClick={onClose}>
          <X className="size-4" />
        </IconButton>
      </div>
      {children}
    </div>
  );
}

export function ScreensSection() {
  const k = useKit();
  const [open, setOpen] = useState<ScreenKey | null>(null);
  const Screen = open ? SCREENS[open] : null;

  return (
    <DebugSection id="screens">
      <Specimen name="FullScreenMessage" usage={k("u.fullScreen")}>
        {(Object.keys(SCREENS) as ScreenKey[]).map((key) => (
          <Button key={key} variant="glass" onClick={() => setOpen(key)}>
            {k(`s.screen.${key}`)}
          </Button>
        ))}
      </Specimen>
      <Specimen name="PageRouteError" usage={k("u.pageRouteError")} stage="stretch">
        <PageRouteError />
      </Specimen>
      {Screen && (
        <ScreenOverlay onClose={() => setOpen(null)}>
          <Screen />
        </ScreenOverlay>
      )}
    </DebugSection>
  );
}
