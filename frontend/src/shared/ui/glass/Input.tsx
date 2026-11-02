import { Check, Copy, Eye, EyeOff } from "lucide-react";
import { useState, type ComponentProps, type ReactNode } from "react";

import { copyToClipboard } from "@shared/lib/clipboard";
import { IconButton } from "@shared/ui/IconButton";

// sunken well; focus, an invalid value (aria-invalid or the browser's own check) and disabled
// are read off the control inside, so the ring sits on the well
const WELL_CLASS =
  "glass-well transition-shadow focus-within:ring-2 focus-within:ring-primary/50 has-[[aria-invalid=true]]:ring-2 has-[[aria-invalid=true]]:ring-error/60 has-[[data-invalid-native]]:ring-2 has-[[data-invalid-native]]:ring-error/60 has-disabled:cursor-not-allowed has-disabled:opacity-40";
// number inputs drop the browser's spinner: the well has no room for it, and arrow keys still step
const CONTROL_CLASS =
  "min-w-0 bg-transparent outline-none placeholder:text-muted-foreground/70 disabled:cursor-not-allowed [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none";
const TEXT_CLASS = "text-[13px] text-foreground";
const MONO_CLASS = "font-mono text-[12px] text-muted-foreground";

const HEIGHT = { sm: "h-8", md: "h-9" } as const;

type InputProps = Omit<ComponentProps<"input">, "size"> & {
  /** md: 36px form field; sm: 32px, inside a Row next to its 32px icon */
  size?: keyof typeof HEIGHT;
  /** unit after the value ("ч", "₽"), muted */
  suffix?: ReactNode;
  /** controls at the end (copy, reveal), on the well's curve */
  end?: ReactNode;
  /** 12px monospace, muted: a machine value (a key) */
  mono?: boolean;
  /** layout only, on the well */
  className?: string;
};

export function Input({ size = "md", suffix, end, mono = false, className = "", ...props }: InputProps) {
  return (
    <label className={`flex cursor-text items-center rounded-full ${HEIGHT[size]} ${WELL_CLASS} ${end ? "pr-1" : ""} ${className}`}>
      {/* size 1: the default 20-character width would hold the well wider than its layout */}
      <input size={1} className={`flex-1 px-3.5 ${CONTROL_CLASS} ${mono ? MONO_CLASS : TEXT_CLASS}`} {...props} />
      {suffix != null && <span className="shrink-0 pr-3.5 text-[13px] text-muted-foreground">{suffix}</span>}
      {end}
    </label>
  );
}

/** Input with a show/hide eye at the end. */
export function PasswordInput(props: Omit<InputProps, "type" | "end" | "mono">) {
  const [isVisible, setIsVisible] = useState(false);
  return (
    <Input
      {...props}
      type={isVisible ? "text" : "password"}
      end={
        <IconButton size="7" onClick={() => setIsVisible((value) => !value)} tabIndex={-1}>
          {isVisible ? <EyeOff className="size-3.5" /> : <Eye className="size-3.5" />}
        </IconButton>
      }
    />
  );
}

/** A read-only machine value (a key) with a copy button at the end; a check for a moment once copied. */
export function CopyInput({ value, ...props }: Omit<InputProps, "value" | "readOnly" | "mono" | "end"> & { value: string }) {
  const [isCopied, setIsCopied] = useState(false);
  const copy = () => {
    void copyToClipboard(value).then((copied) => {
      if (!copied) return;
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 1500);
    });
  };
  return (
    <Input
      {...props}
      mono
      readOnly
      value={value}
      end={
        <IconButton size="7" onClick={copy}>
          {isCopied ? <Check className="size-3.5 text-primary" /> : <Copy className="size-3.5" />}
        </IconButton>
      }
    />
  );
}

/** Multiline field, 18px corners (a 36px field's). corner: a badge over the bottom right (a counter).
 *  className: layout only, on the well. */
export function TextArea({
  corner,
  mono = false,
  className = "",
  ...props
}: ComponentProps<"textarea"> & { corner?: ReactNode; mono?: boolean }) {
  return (
    <label className={`relative flex cursor-text overflow-hidden rounded-[18px] ${WELL_CLASS} ${className}`}>
      <textarea
        className={`w-full resize-none px-3.5 py-3 leading-5 ${CONTROL_CLASS} ${mono ? "font-mono text-[12px] text-foreground" : TEXT_CLASS}`}
        {...props}
      />
      {corner && (
        <span className="glass-control pointer-events-none absolute bottom-3 right-3 rounded-full px-2 py-0.5 text-[11px] tabular-nums text-muted-foreground">
          {corner}
        </span>
      )}
    </label>
  );
}
