import type { CSSProperties } from "react";

interface SliderProps {
  value: number;
  onChange: (value: number) => void;
  max: number;
  disabled?: boolean;
  className?: string;
}

export function Slider({ value, onChange, max, disabled = false, className = "" }: SliderProps) {
  const fill = (Math.min(Math.max(value, 0), max) / max) * 100;
  return (
    <input
      type="range"
      min={0}
      max={max}
      value={value}
      disabled={disabled}
      onChange={(event) => onChange(Number(event.target.value))}
      style={{ "--fill": `${fill}%` } as CSSProperties}
      className={`slider ${className}`}
    />
  );
}
