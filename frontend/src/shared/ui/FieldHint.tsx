import { CircleHelp } from "lucide-react";

interface FieldHintProps {
  text: string;
  side?: "top" | "bottom";
  /** "end" keeps the bubble inside the panel when the icon sits at its right
   * edge -- centered, it would be clipped by the scroll container. */
  align?: "center" | "end";
}

export function FieldHint({ text, side = "top", align = "center" }: FieldHintProps) {
  return (
    <span tabIndex={-1} className="group relative inline-flex outline-none">
      <CircleHelp className="size-3.5 shrink-0 cursor-help text-muted-foreground" aria-hidden="true" />
      <span
        role="tooltip"
        className={`pointer-events-none absolute z-20 w-56 rounded-popover-item border border-white/[0.14] bg-popover/60 whitespace-pre-line px-3 py-2 text-xs font-normal normal-case text-foreground opacity-0 shadow-[0_24px_48px_-20px_rgba(4,8,20,0.6)] backdrop-blur-2xl backdrop-saturate-150 transition-opacity duration-150 group-hover:opacity-100 group-focus-within:opacity-100 ${
          side === "top" ? "bottom-full mb-2" : "top-full mt-2"
        } ${align === "end" ? "right-0" : "left-1/2 -translate-x-1/2"}`}
      >
        {text}
      </span>
    </span>
  );
}
