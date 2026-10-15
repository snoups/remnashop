import {
  deletePushSubscription,
  getPushPublicKey,
  listPushSubscriptions,
  subscribePush,
} from "@entities/notifications/api";
import { disablePush } from "@shared/lib/push";
import type { PushApi } from "@shared/lib/push";

export const pushApi: PushApi = {
  getPublicKey: async () => (await getPushPublicKey()).public_key,
  subscribe: subscribePush,
  listEndpoints: async () => (await listPushSubscriptions()).items,
  remove: deletePushSubscription,
};

const SIGN_OUT_PUSH_TIMEOUT_MS = 2000;

// before a sign-out: the next admin in this browser shouldn't get this one's
// notifications; capped, since a hung push service mustn't hold the logout
export async function disablePushOnSignOut(): Promise<void> {
  await Promise.race([
    disablePush(pushApi, { optOut: false }).catch(() => undefined),
    new Promise((resolve) => setTimeout(resolve, SIGN_OUT_PUSH_TIMEOUT_MS)),
  ]);
}
