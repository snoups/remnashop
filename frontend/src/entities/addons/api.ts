import { apiGet } from "@shared/api/http";
import type { ListResponse } from "@shared/api/http";

// Read-only: feeds the promocode reward picker (TRAFFIC/DEVICES rewards point at an add-on).
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
