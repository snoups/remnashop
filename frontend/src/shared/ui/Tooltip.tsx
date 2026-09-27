// Sits inside the control it describes -- that control needs `group relative`.
// aria-hidden because the control already carries the same text as its
// aria-label; this is the visible half only.
export function Tooltip({ text }: { text: string }) {
  return (
    <span
      role="tooltip"
      aria-hidden
      className="pointer-events-none absolute left-full top-1/2 z-50 ml-3.5 w-max max-w-56 -translate-y-1/2 rounded-popover-item border border-white/[0.14] bg-popover/60 px-3 py-2 text-left text-xs font-normal normal-case text-foreground opacity-0 shadow-[0_24px_48px_-20px_rgba(4,8,20,0.6)] backdrop-blur-2xl backdrop-saturate-150 transition-opacity duration-150 group-hover:opacity-100 group-focus-visible:opacity-100"
    >
      {text}
    </span>
  );
}
