import type { Admin } from "@entities/admin/api";
import type { Role } from "@shared/types/rbac";
import type { BadgeTone } from "@shared/ui/Badge";

export const ROLE_BADGE_TONE: Record<Role, BadgeTone> = {
  USER: "neutral",
  ADMIN: "neutral",
  OWNER: "accent",
  SYSTEM: "warning",
};

export function getAdminInitials(admin: Admin): string {
  return (admin.login ?? admin.name).slice(0, 2).toUpperCase();
}
