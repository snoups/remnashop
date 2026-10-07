import {
  deletePushSubscription,
  getPushPublicKey,
  listPushSubscriptions,
  subscribePush,
} from "@entities/notifications/api";
import type { PushApi } from "@shared/lib/push";

export const pushApi: PushApi = {
  getPublicKey: async () => (await getPushPublicKey()).public_key,
  subscribe: subscribePush,
  listEndpoints: async () => (await listPushSubscriptions()).items,
  remove: deletePushSubscription,
};
