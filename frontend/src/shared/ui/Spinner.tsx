import { Loader2 } from "lucide-react";
import { useEffect, useState } from "react";

import { STATE_PADDING } from "@shared/ui/glass/EmptyState";

// A load that settles faster than this never shows a spinner at all, instead of flashing one.
const SHOW_DELAY_MS = 150;

interface SpinnerProps {
  /** EmptyState's heights, so "loading -> empty" doesn't jump */
  size?: keyof typeof STATE_PADDING;
  className?: string;
}

export function Spinner({ size, className = "" }: SpinnerProps) {
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setIsVisible(true), SHOW_DELAY_MS);
    return () => clearTimeout(timer);
  }, []);

  return (
    <div className={`flex flex-1 items-center justify-center text-muted-foreground ${size ? STATE_PADDING[size] : ""} ${className}`}>
      {isVisible && <Loader2 className="size-5 animate-spin" />}
    </div>
  );
}

/** Corner spinner over a loaded card while it refetches; the card needs `relative`. */
export function RefetchSpinner() {
  return <Loader2 className="absolute right-4 top-4 size-3.5 animate-spin text-muted-foreground" />;
}
