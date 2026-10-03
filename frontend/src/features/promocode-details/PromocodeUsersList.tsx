import { useTranslation } from "react-i18next";
import { useOpenEntity } from "@shared/lib/entity-dialogs";
import { formatDateTime } from "@shared/lib/relative-time";

import {
  listPromocodeActivatedUsers,
  type Promocode,
  type PromocodeActivatedUser,
} from "@entities/promocodes/api";
import { usePaginatedList } from "@shared/lib/use-paginated-list";
import { EmptyState, ErrorState } from "@shared/ui/EmptyState";
import { LoadMoreButton } from "@shared/ui/LoadMoreButton";
import { Spinner } from "@shared/ui/Spinner";
import { Card } from "@shared/ui/Card";
import { Tag } from "@shared/ui/Tag";
import { UserRow } from "@shared/ui/UserRow";

const USERS_PAGE_SIZE = 10;

export function PromocodeUsersList({ promocode }: { promocode: Promocode }) {
  const { t, i18n } = useTranslation();
  const { openUser: openUserCard } = useOpenEntity();
  const { state, isLoadingMore, hasMore, loadMore } = usePaginatedList(
    (id: number, page, signal) => listPromocodeActivatedUsers(id, page, USERS_PAGE_SIZE, signal),
    promocode.id,
  );

  const openUser = (user: PromocodeActivatedUser) => {
    openUserCard(user.user_id);
  };

  return (
    <Card variant="list">
      {state.kind === "loading" && <Spinner size="card" />}
      {state.kind === "error" && <ErrorState text={t("promocodes.details.usersLoadError")} />}
      {state.kind === "ready" && state.items.length === 0 && (
        <EmptyState text={t("promocodes.details.usersEmpty")} />
      )}
      {state.kind === "ready" &&
        state.items.map((user) => (
          <UserRow
            key={user.activation_id}
            name={user.name}
            subtitle={formatDateTime(user.activated_at, i18n.language)}
            aside={user.subscription_id !== null && <Tag>#{user.subscription_id}</Tag>}
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
    </Card>
  );
}
