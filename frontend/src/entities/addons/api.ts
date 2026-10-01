import { apiGet } from "@shared/api/http";
import type { ListResponse } from "@shared/api/http";

// Read-only: add-on management itself has no dashboard page yet, this exists
// only to power the promocode reward picker (TRAFFIC/DEVICES reward types
// reference an existing add-on by id).
export type AddOnType = "TRAFFIC" | "DEVICES";

export interface AddOnListItem {
  id: number;
  name: string;
  type: AddOnType;
  amount: number;
  is_active: boolean;
}

export function listAddons(signal?: AbortSignal): Promise<AddOnListItem[]> {
  return apiGet<ListResponse<AddOnListItem>>("/addons", signal).then((response) => response.items);
}
