import { DebugSection, Specimen } from "@pages/debug/debug-ui";
import { useKit } from "@pages/debug/use-kit";
import { EYEBROW_CLASS, KPI_VALUE_CLASS, SCREEN_TITLE_CLASS, STAT_VALUE_CLASS } from "@shared/ui/classes";

// one row per step of the scale, largest first; className is what the code uses for that role
const STEPS = [
  { key: "kpi", px: 24, token: "text-2xl · KPI_VALUE_CLASS", className: `${KPI_VALUE_CLASS} text-foreground` },
  { key: "screen", px: 20, token: "text-xl · SCREEN_TITLE_CLASS", className: SCREEN_TITLE_CLASS },
  { key: "header", px: 18, token: "text-lg", className: "text-lg font-semibold tracking-tight text-foreground" },
  { key: "title", px: 16, token: "text-base", className: "text-base font-semibold tracking-tight text-foreground" },
  { key: "stat", px: 16, token: "text-base · STAT_VALUE_CLASS", className: `${STAT_VALUE_CLASS} text-foreground` },
  { key: "body", px: 14, token: "text-sm", className: "text-sm text-foreground" },
  { key: "secondary", px: 12, token: "text-xs", className: "text-xs text-muted-foreground" },
  { key: "eyebrow", px: 12, token: "text-xs · EYEBROW_CLASS", className: EYEBROW_CLASS },
  { key: "counter", px: 11, token: "text-[11px]", className: "text-[11px] font-semibold text-foreground" },
] as const;

const EXCEPTIONS = ["headerAccount", "emoji", "avatar", "recap"] as const;

export function TypographySection() {
  const k = useKit();
  return (
    <DebugSection id="typography">
      <Specimen name="text-*" usage={k("u.typeScale")} wide stage="stretch">
        {STEPS.map(({ key, px, token, className }) => (
          <div key={key} className="grid grid-cols-[48px_minmax(0,1fr)_minmax(0,1fr)] items-baseline gap-4 border-b border-white/[0.06] pb-3 last:border-0 last:pb-0">
            <span className="font-mono text-xs text-muted-foreground">{px}px</span>
            <span className={`truncate ${className}`}>{k(`s.type.${key}.sample`)}</span>
            <span className="flex min-w-0 flex-col">
              <span className="truncate text-xs text-foreground">{k(`s.type.${key}.role`)}</span>
              <span className="truncate font-mono text-xs text-muted-foreground">{token}</span>
            </span>
          </div>
        ))}
      </Specimen>
      <Specimen name="text-[Npx]" usage={k("u.typeExceptions")} wide stage="stretch">
        <ul className="flex flex-col gap-1.5 text-sm text-foreground">
          {EXCEPTIONS.map((key) => (
            <li key={key}>{k(`s.typeException.${key}`)}</li>
          ))}
        </ul>
      </Specimen>
    </DebugSection>
  );
}
