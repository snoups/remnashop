import { Loader2 } from "lucide-react";

interface SpinnerProps {
  className?: string;
}

export function Spinner({ className = "" }: SpinnerProps) {
  return (
    <div className={`flex items-center justify-center text-muted-foreground ${className}`}>
      <Loader2 className="size-5 animate-spin" />
    </div>
  );
}
