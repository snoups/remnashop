import { FlaskConical } from "lucide-react";

import { DebugShell } from "@pages/debug/debug-ui";
import { useKit } from "@pages/debug/use-kit";
import { EmptyState } from "@shared/ui/glass/EmptyState";

// Live copies of markup being redesigned, beside the current one, until the new one is signed off.
export function DebugVariantsPage() {
  const k = useKit();
  return (
    <DebugShell>
      <p className="px-1 text-[12px] text-muted-foreground">{k("variants.caption")}</p>
      <EmptyState text={k("variants.empty")} icon={FlaskConical} />
    </DebugShell>
  );
}
