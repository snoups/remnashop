import type { CSSProperties } from "react";

interface SliderProps {
  value: number;
  onChange: (value: number) => void;
  min?: number;
  max: number;
  step?: number;
  disabled?: boolean;
  className?: string;
}

export function Slider({ value, onChange, min = 0, max, step = 1, disabled = false, className = "" }: SliderProps) {
  const fill = ((Math.min(Math.max(value, min), max) - min) / (max - min)) * 100;
  return (
    <input
      type="range"
      min={min}
      max={max}
      step={step}
      value={value}
      disabled={disabled}
      onChange={(event) => onChange(Number(event.target.value))}
      style={{ "--fill": `${fill}%` } as CSSProperties}
      className={`slider ${className}`}
    />
  );
}
