import { motion } from "motion/react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { formatDateTime } from "@shared/lib/relative-time";
import { useNavigate } from "react-router-dom";

import {
  listPromocodeActivatedUsers,
  type Promocode,
  type PromocodeActivatedUser,
} from "@entities/promocodes/api";
import { userCardLink } from "@entities/user/api";
import { bounceTap } from "@shared/lib/bounceState";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { EmptyState } from "@shared/ui/EmptyState";
import { LoadMoreButton } from "@shared/ui/LoadMoreButton";
import { Spinner } from "@shared/ui/Spinner";
import { Card } from "@shared/ui/Card";
import { Tag } from "@shared/ui/Tag";

const USERS_PAGE_SIZE = 10;

export function PromocodeUsersList({ promocode }: { promocode: Promocode }) {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const [state, , setData] = useAsyncResource((signal) =>
    listPromocodeActivatedUsers(promocode.id, 1, USERS_PAGE_SIZE, signal),
  );
  const [page, setPage] = useState(1);
  const [isLoadingMore, setIsLoadingMore] = useState(false);

  const handleLoadMore = async () => {
    if (state.kind !== "ready") return;
    setIsLoadingMore(true);
    try {
      const result = await listPromocodeActivatedUsers(promocode.id, page + 1, USERS_PAGE_SIZE);
      setData({ ...result, items: [...state.data.items, ...result.items] });
      setPage(page + 1);
    } catch {
      // keep current items; the button stays available to retry
    } finally {
      setIsLoadingMore(false);
    }
  };

  const openUser = (user: PromocodeActivatedUser) => {
    const link = userCardLink({ id: user.user_id, name: user.name });
    navigate(link.to, { state: link.state });
  };

  return (
    <Card variant="list">
      {state.kind === "loading" && <Spinner size="card" />}
      {state.kind === "error" && <p className="p-3 text-sm text-error">{t("promocodes.details.usersLoadError")}</p>}
      {state.kind === "ready" && state.data.items.length === 0 && (
        <EmptyState text={t("promocodes.details.usersEmpty")} />
      )}
      {state.kind === "ready" &&
        state.data.items.map((user) => (
          <motion.button
            key={user.activation_id}
            type="button"
            onClick={() => openUser(user)}
            {...bounceTap(0.03)}
            className="flex w-full items-center gap-3 rounded-full px-2.5 py-2 text-left transition-colors hover:bg-white/[0.04]"
          >
            <span
              className="flex size-8 shrink-0 items-center justify-center rounded-full bg-white/[0.06] text-[12px] font-bold text-foreground"
            >
              {user.name ? user.name.slice(0, 2).toUpperCase() : "?"}
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-[13px] font-medium leading-tight text-foreground/90">{user.name || t("users.deleted.name")}</p>
              <p className="text-[11.5px] leading-tight text-muted-foreground">
                {formatDateTime(user.activated_at, i18n.language)}
              </p>
            </div>
            {user.subscription_id !== null && <Tag>#{user.subscription_id}</Tag>}
          </motion.button>
        ))}
      {state.kind === "ready" && state.data.items.length < state.data.total && (
        <div className="px-2.5 py-1">
          <LoadMoreButton
            onClick={() => void handleLoadMore()}
            isLoading={isLoadingMore}
            shown={state.data.items.length}
            total={state.data.total}
          />
        </div>
      )}
    </Card>
  );
}
