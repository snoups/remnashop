import { CircleHelp } from "lucide-react";

interface FieldHintProps {
  text: string;
}

export function FieldHint({ text }: FieldHintProps) {
  return (
    <span tabIndex={-1} className="group relative inline-flex outline-none">
      <CircleHelp className="size-3.5 shrink-0 cursor-help text-muted-foreground" aria-hidden="true" />
      <span
        role="tooltip"
        className="pointer-events-none absolute bottom-full left-1/2 z-20 mb-2 w-56 -translate-x-1/2 rounded-popover-item border border-white/[0.14] bg-popover/60 px-3 py-2 text-xs font-normal normal-case text-foreground opacity-0 shadow-[0_24px_48px_-20px_rgba(4,8,20,0.6)] backdrop-blur-2xl backdrop-saturate-150 transition-opacity duration-150 group-hover:opacity-100 group-focus-within:opacity-100"
      >
        {text}
      </span>
    </span>
  );
}
