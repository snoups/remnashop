import { DebugShell } from "@pages/debug/debug-ui";
import { useKit } from "@pages/debug/use-kit";

// Live copies of markup being redesigned, beside the current one, until the new one is signed off.
export function DebugVariantsPage() {
  const k = useKit();
  return (
    <DebugShell>
      <p className="px-1 text-xs text-muted-foreground">{k("variants.caption")}</p>
    </DebugShell>
  );
}
