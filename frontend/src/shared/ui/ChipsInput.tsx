import { X } from "lucide-react";
import { useLayoutEffect, useRef, useState, type ClipboardEvent, type KeyboardEvent } from "react";

import { IconButton } from "@shared/ui/IconButton";

const SINGLE_ROW_HEIGHT = 38;
// the glass well (shared/ui/glass) is 36px: 24px chips 6px in, concentric with its 18px corners
const GLASS_SINGLE_ROW_HEIGHT = 36;

interface ChipsInputProps {
  id?: string;
  values: string[];
  onChange: (values: string[]) => void;
  /** the stored form of a token, or null when it isn't valid */
  normalize: (token: string) => string | null;
  placeholder?: string;
  inputMode?: "numeric" | "email" | "text";
  /** the glass design's sunken well and type scale */
  glass?: boolean;
}

/** Tokens split on Enter, comma, space or paste; a token that fails `normalize` stays in the input, marked. */
export function ChipsInput({ id, values, onChange, normalize, placeholder, inputMode = "text", glass = false }: ChipsInputProps) {
  const [draft, setDraft] = useState("");
  const [isInvalid, setIsInvalid] = useState(false);
  const boxRef = useRef<HTMLDivElement>(null);
  const [isWrapped, setIsWrapped] = useState(false);

  // one row is a pill like TextInput; wrapped rows get TextArea's corners
  useLayoutEffect(() => {
    const box = boxRef.current;
    if (!box) return;
    const rowHeight = glass ? GLASS_SINGLE_ROW_HEIGHT : SINGLE_ROW_HEIGHT;
    const observer = new ResizeObserver(() => setIsWrapped(box.offsetHeight > rowHeight));
    observer.observe(box);
    return () => observer.disconnect();
  }, [glass]);

  const commit = (text: string) => {
    const accepted: string[] = [];
    const rejected: string[] = [];
    for (const token of text.split(/[\s,;]+/).filter(Boolean)) {
      const value = normalize(token);
      if (value === null) rejected.push(token);
      else if (!values.includes(value) && !accepted.includes(value)) accepted.push(value);
    }
    if (accepted.length > 0) onChange([...values, ...accepted]);
    setDraft(rejected.join(" "));
    setIsInvalid(rejected.length > 0);
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter" || event.key === "," || event.key === " ") {
      event.preventDefault();
      commit(draft);
    } else if (event.key === "Backspace" && draft === "" && values.length > 0) {
      onChange(values.slice(0, -1));
    }
  };

  const handlePaste = (event: ClipboardEvent<HTMLInputElement>) => {
    event.preventDefault();
    commit(`${draft} ${event.clipboardData.getData("text")}`);
  };

  return (
    <div
      ref={boxRef}
      className={
        glass
          ? `glass-well flex min-h-9 flex-wrap items-center gap-1.5 rounded-[18px] p-1.5 transition-shadow ${
              isInvalid ? "ring-2 ring-error/60" : "focus-within:ring-2 focus-within:ring-primary/50"
            }`
          : `flex min-h-9.5 flex-wrap items-center gap-1.5 ${isWrapped ? "rounded-xl" : "rounded-[19px]"} border bg-input/60 p-1.5 ${
              isInvalid ? "border-error" : "border-border focus-within:border-primary"
            }`
      }
    >
      {values.map((value) => (
        <span
          key={value}
          className={`flex h-6 items-center gap-1 rounded-full bg-white/[0.06] pl-2.5 pr-0.5 font-mono text-foreground ${
            glass ? "text-[12px]" : "text-[12.5px]"
          }`}
        >
          {value}
          <IconButton size="18px" onClick={() => onChange(values.filter((other) => other !== value))}>
            <X className="size-2.5" />
          </IconButton>
        </span>
      ))}
      <input
        id={id}
        inputMode={inputMode}
        value={draft}
        onChange={(event) => {
          setDraft(event.target.value);
          setIsInvalid(false);
        }}
        onKeyDown={handleKeyDown}
        onPaste={handlePaste}
        onBlur={() => commit(draft)}
        placeholder={values.length === 0 ? placeholder : undefined}
        aria-invalid={isInvalid}
        className={`h-6 min-w-16 flex-1 bg-transparent px-1.5 font-mono text-foreground outline-none ${
          glass ? "text-[13px]" : "text-sm"
        }`}
      />
    </div>
  );
}
