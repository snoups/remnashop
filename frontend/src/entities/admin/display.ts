import type { Admin } from "@entities/admin/api";
import type { Role } from "@shared/types/rbac";

export const ROLE_BADGE_CLASSNAME: Record<Role, string> = {
  USER: "border-border bg-white/[0.04] text-muted-foreground",
  ADMIN: "border-border bg-white/[0.06] text-foreground/80",
  OWNER: "border-primary/40 bg-accent text-primary",
  SYSTEM: "border-warning/30 bg-warning/10 text-warning",
};

export function getAdminInitials(admin: Admin): string {
  return (admin.login ?? admin.name).slice(0, 2).toUpperCase();
}
