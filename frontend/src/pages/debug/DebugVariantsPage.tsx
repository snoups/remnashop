import { useKit } from "@pages/debug/use-kit";
import { GlassSettingsMockup } from "@pages/debug/GlassSettingsMockup";

// Live copies of markup that drifted apart across pages, side by side, until one is picked for shared/ui.
export function DebugVariantsPage() {
  const k = useKit();

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-[21px] font-bold tracking-tight text-foreground">{k("variants.title")}</h1>
        <p className="text-[12.5px] text-muted-foreground">{k("variants.caption")}</p>
      </div>

      <GlassSettingsMockup />
    </div>
  );
}
