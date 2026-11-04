import { useTranslation } from "react-i18next";
import { useOpenEntity } from "@shared/lib/entity-dialogs";
import { formatDateTime } from "@shared/lib/relative-time";

import { type AdLink, type AttributedUser, listAdLinkAttributedUsers } from "@entities/advertising/api";
import { usePaginatedList } from "@shared/lib/use-paginated-list";
import { EmptyState, ErrorState } from "@shared/ui/glass/EmptyState";
import { LoadMoreButton } from "@shared/ui/LoadMoreButton";
import { Spinner } from "@shared/ui/Spinner";
import { Badge } from "@shared/ui/Badge";
import { DialogCard } from "@shared/ui/glass/DialogCard";
import { UserRow } from "@shared/ui/UserRow";

const USERS_PAGE_SIZE = 10;

export function AdLinkUsersList({ adLink }: { adLink: AdLink }) {
  const { t, i18n } = useTranslation();
  const { openUser: openUserCard } = useOpenEntity();
  const { state, isLoadingMore, hasMore, loadMore } = usePaginatedList(
    (id: number, page, signal) => listAdLinkAttributedUsers(id, page, USERS_PAGE_SIZE, signal),
    adLink.id,
    (user) => user.user_id,
  );

  const openUser = (user: AttributedUser) => {
    openUserCard(user.user_id);
  };

  return (
    <DialogCard>
      {state.kind === "loading" && <Spinner size="card" />}
      {state.kind === "error" && <ErrorState text={t("common.loadError")} />}
      {state.kind === "ready" && state.items.length === 0 && (
        <EmptyState text={t("advertising.stats.usersEmpty")} />
      )}
      {state.kind === "ready" &&
        state.items.map((user) => (
          <UserRow
            key={user.user_id}
            name={user.name}
            subtitle={`${t(`advertising.channel.${user.channel}`)} · ${formatDateTime(user.created_at, i18n.language)}`}
            aside={
              <Badge borderless tone={user.has_paid ? "success" : "neutral"}>
                {user.has_paid ? t("advertising.stats.hasPaid") : t("advertising.stats.notPaid")}
              </Badge>
            }
            onClick={() => openUser(user)}
          />
        ))}
      {state.kind === "ready" && hasMore && (
        <div className="px-2.5 py-1">
          <LoadMoreButton
            onClick={() => void loadMore()}
            isLoading={isLoadingMore}
            shown={state.items.length}
            total={state.total}
          />
        </div>
      )}
    </DialogCard>
  );
}
