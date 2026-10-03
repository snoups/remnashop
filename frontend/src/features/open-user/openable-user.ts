import { usePermissions } from "@entities/user/use-current-user";

export interface OpenableUser {
  id?: number | null;
  role?: string | null;
}

// id 0 and below is a synthetic actor (API token / system)
export function isOpenableUser(user: OpenableUser | null | undefined): user is OpenableUser & { id: number } {
  return !!user?.id && user.id > 0 && user.role !== "SYSTEM";
}

export function useCanOpenUsers(): boolean {
  return usePermissions().includes("USERS_DETAIL_VIEW");
}
