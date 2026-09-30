import { motion } from "motion/react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { formatDateTime } from "@shared/lib/relative-time";
import { useNavigate } from "react-router-dom";

import { type AdLink, type AttributedUser, listAdLinkAttributedUsers } from "@entities/advertising/api";
import { userCardLink } from "@entities/user/api";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { EmptyState } from "@shared/ui/EmptyState";
import { LoadMoreButton } from "@shared/ui/LoadMoreButton";
import { Spinner } from "@shared/ui/Spinner";
import { Badge } from "@shared/ui/Badge";
import { Card } from "@shared/ui/Card";

const USERS_PAGE_SIZE = 10;

export function AdLinkUsersList({ adLink }: { adLink: AdLink }) {
  const { t, i18n } = useTranslation();
  const bounceStrength = useBounceStrength();
  const navigate = useNavigate();
  const [state, , setData] = useAsyncResource((signal) =>
    listAdLinkAttributedUsers(adLink.id, 1, USERS_PAGE_SIZE, signal),
  );
  const [page, setPage] = useState(1);
  const [isLoadingMore, setIsLoadingMore] = useState(false);

  const handleLoadMore = async () => {
    if (state.kind !== "ready") return;
    setIsLoadingMore(true);
    try {
      const result = await listAdLinkAttributedUsers(adLink.id, page + 1, USERS_PAGE_SIZE);
      setData({ ...result, items: [...state.data.items, ...result.items] });
      setPage(page + 1);
    } catch {
      // keep current items; the button stays available to retry
    } finally {
      setIsLoadingMore(false);
    }
  };

  const openUser = (user: AttributedUser) => {
    const link = userCardLink({ id: user.user_id, name: user.name });
    navigate(link.to, { state: link.state });
  };

  return (
    <Card variant="list">
      {state.kind === "loading" && <Spinner size="card" />}
      {state.kind === "error" && <p className="p-3 text-sm text-error">{t("advertising.stats.loadError")}</p>}
      {state.kind === "ready" && state.data.items.length === 0 && (
        <EmptyState text={t("advertising.stats.usersEmpty")} />
      )}
      {state.kind === "ready" &&
        state.data.items.map((user) => (
          <motion.button
            key={user.user_id}
            type="button"
            onClick={() => openUser(user)}
            {...bounceTap(bounceStrength, 0.03)}
            className="flex w-full items-center gap-3 rounded-full px-2.5 py-2 text-left transition-colors hover:bg-white/[0.04]"
          >
            <span
              aria-hidden
              className="flex size-8 shrink-0 items-center justify-center rounded-full bg-white/[0.06] text-[12px] font-bold text-foreground"
            >
              {user.name ? user.name.slice(0, 2).toUpperCase() : "?"}
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-[13px] font-medium leading-tight text-foreground/90">{user.name || t("users.deleted.name")}</p>
              <p className="text-[11.5px] leading-tight text-muted-foreground">
                {t(`advertising.channel.${user.channel}`)} &middot; {formatDateTime(user.created_at, i18n.language)}
              </p>
            </div>
            <Badge tone={user.has_paid ? "success" : "neutral"}>
              {user.has_paid ? t("advertising.stats.hasPaid") : t("advertising.stats.notPaid")}
            </Badge>
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
