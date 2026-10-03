import { Gift, Info, MessageCircle, Send, Sparkles, TriangleAlert } from "lucide-react";
import type { LucideIcon } from "lucide-react";

// the backend already coerces unknown names to "info"; the fallback covers an older bundle
const ICONS: Record<string, LucideIcon> = {
  info: Info,
  warning: TriangleAlert,
  sparkles: Sparkles,
  message: MessageCircle,
  gift: Gift,
  telegram: Send,
};

export function AnnouncementIcon({ icon, className }: { icon: string; className?: string }) {
  const Icon = ICONS[icon] ?? Info;
  return <Icon className={className} />;
}
