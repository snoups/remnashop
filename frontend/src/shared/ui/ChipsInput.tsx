import { X } from "lucide-react";
import { useState, type ClipboardEvent, type KeyboardEvent } from "react";

import { IconButton } from "@shared/ui/IconButton";

interface ChipsInputProps {
  id?: string;
  values: string[];
  onChange: (values: string[]) => void;
  /** the stored form of a token, or null when it isn't valid */
  normalize: (token: string) => string | null;
  placeholder?: string;
  inputMode?: "numeric" | "email" | "text";
}

/** Tokens split on Enter, comma, space or paste; a token that fails `normalize` stays in the input, marked. */
export function ChipsInput({ id, values, onChange, normalize, placeholder, inputMode = "text" }: ChipsInputProps) {
  const [draft, setDraft] = useState("");
  const [isInvalid, setIsInvalid] = useState(false);

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
      className={`flex min-h-9.5 flex-wrap items-center gap-1.5 rounded-[19px] border bg-input/60 px-1.5 py-1 ${
        isInvalid ? "border-error" : "border-border focus-within:border-primary"
      }`}
    >
      {values.map((value) => (
        <span
          key={value}
          className="flex items-center gap-1 rounded-full bg-white/[0.06] py-0.5 pl-2.5 pr-0.5 font-mono text-[12.5px] text-foreground"
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
        className="min-w-36 flex-1 bg-transparent px-1.5 py-1 font-mono text-sm text-foreground outline-none"
      />
    </div>
  );
}
