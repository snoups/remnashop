import { Loader2 } from "lucide-react";
import { useEffect, useState } from "react";

// A load that settles faster than this never shows a spinner at all, instead of flashing one.
const SHOW_DELAY_MS = 150;

// Same heights as EmptyState, so "loading -> empty" doesn't jump.
const PADDING = {
  page: "py-12",
  card: "py-8",
} as const;

interface SpinnerProps {
  size?: keyof typeof PADDING;
  className?: string;
}

export function Spinner({ size, className = "" }: SpinnerProps) {
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setIsVisible(true), SHOW_DELAY_MS);
    return () => clearTimeout(timer);
  }, []);

  return (
    <div className={`flex items-center justify-center text-muted-foreground ${size ? PADDING[size] : ""} ${className}`}>
      {isVisible && <Loader2 className="size-5 animate-spin" />}
    </div>
  );
}

/** Corner spinner over a loaded card while it refetches; the card needs `relative`. */
export function RefetchSpinner() {
  return <Loader2 className="absolute right-4 top-4 size-3.5 animate-spin text-muted-foreground" />;
}
