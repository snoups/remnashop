import type { ComponentType } from "react";

type OptionIcon = ComponentType<{ className?: string }>;

// SelectOption.icon slot: sized/positioned by the caller's className, content centered inside.
export function dotIcon(colorClassName: string): OptionIcon {
  return function DotIcon({ className }) {
    return (
      <span className={`${className ?? ""} flex items-center justify-center`}>
        <span className={`size-2 rounded-full ${colorClassName}`} />
      </span>
    );
  };
}

// matches GatewaySettingsCard's first-letter avatar
export function letterIcon(label: string): OptionIcon {
  return function LetterIcon({ className }) {
    // SVG text scales with the viewBox, so the letter follows the icon size
    return (
      <svg viewBox="0 0 14 14" className={`${className ?? ""} rounded-full bg-white/[0.1] text-foreground`}>
        <text x="7" y="7" textAnchor="middle" dominantBaseline="central" fontSize="9" fontWeight="700" fill="currentColor">
          {label.charAt(0)}
        </text>
      </svg>
    );
  };
}
