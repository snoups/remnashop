import { motion } from "motion/react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { type InvitedUser, listInvitedUsers } from "@entities/referrals/api";
import { userCardLink } from "@entities/user/api";
import { PillTabs } from "@features/dialog-canvas-editor/PillTabs";
import { formatRewardAmounts, initials, userHandle } from "@features/user-referrals/format";
import { bounceTap } from "@shared/lib/bounceState";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { useDebouncedValue } from "@shared/lib/use-debounced-value";
import { Badge } from "@shared/ui/Badge";
import { Card } from "@shared/ui/Card";
import { EmptyState } from "@shared/ui/EmptyState";
import { LoadMoreButton } from "@shared/ui/LoadMoreButton";
import { SearchField } from "@shared/ui/SearchField";
import { Spinner } from "@shared/ui/Spinner";
import { formatDate } from "@shared/lib/relative-time";

const PAGE_SIZE = 10;
const SEARCH_DEBOUNCE_MS = 200;
const LEVELS = [1, 2, 3];

export function InvitedUsersList({ userId }: { userId: number }) {
  const { t } = useTranslation();
  const [level, setLevel] = useState<number | undefined>(undefined);
  const [searchInput, setSearchInput] = useState("");
  const search = useDebouncedValue(searchInput, SEARCH_DEBOUNCE_MS);

  return (
    <div className="flex flex-col gap-2.5">
      <div className="grid grid-cols-2 items-end gap-2">
        <SearchField
          id={`referral-invited-search-${userId}`}
          label={t("referrals.list.search")}
          hideLabel
          placeholder={t("referrals.dialog.searchPlaceholder")}
          value={searchInput}
          onChange={setSearchInput}
        />
        <div className="min-w-0">
          <PillTabs
            items={[
              { key: "ALL", label: t("referrals.dialog.levelAll") },
              ...LEVELS.map((value) => ({ key: String(value), label: String(value) })),
            ]}
            activeKey={level === undefined ? "ALL" : String(level)}
            onSelect={(key) => setLevel(key === "ALL" ? undefined : Number(key))}
            size="field"
          />
        </div>
      </div>
      {/* keyed by filters: a change remounts and refetches from page 1 */}
      <InvitedUsersPage key={`${level}-${search}`} userId={userId} level={level} search={search} />
    </div>
  );
}

function InvitedUsersPage({ userId, level, search }: { userId: number; level?: number; search: string }) {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const filters = { level, search: search || undefined, pageSize: PAGE_SIZE };
  const [state, , setData] = useAsyncResource((signal) => listInvitedUsers(userId, filters, signal));
  const [page, setPage] = useState(1);
  const [isLoadingMore, setIsLoadingMore] = useState(false);

  const handleLoadMore = async () => {
    if (state.kind !== "ready") return;
    setIsLoadingMore(true);
    try {
      const result = await listInvitedUsers(userId, { ...filters, page: page + 1 });
      setData({ ...result, items: [...state.data.items, ...result.items] });
      setPage(page + 1);
    } catch {
      // keep current items; the button stays available to retry
    } finally {
      setIsLoadingMore(false);
    }
  };

  const openUser = (item: InvitedUser) => {
    if (!item.user) return;
    const link = userCardLink(item.user);
    navigate(link.to, { state: link.state });
  };

  const subtitle = (item: InvitedUser): string =>
    [
      item.user ? userHandle(item.user) : null,
      item.via ? t("referrals.dialog.via", { name: item.via.name }) : null,
      item.created_at
        ? formatDate(item.created_at, i18n.language)
        : null,
    ]
      .filter(Boolean)
      .join(" · ");

  return (
    <Card variant="list">
      {state.kind === "loading" && <Spinner size="card" />}
      {state.kind === "error" && <p className="p-3 text-sm text-error">{t("referrals.dialog.invitedLoadError")}</p>}
      {state.kind === "ready" && state.data.items.length === 0 && (
        <EmptyState text={t("referrals.dialog.invitedEmpty")} />
      )}
      {state.kind === "ready" &&
        state.data.items.map((item, index) => {
          const rewards = formatRewardAmounts(t, item.reward_amounts);
          return (
            <motion.button
              key={item.user?.id ?? `deleted-${index}`}
              type="button"
              disabled={!item.user}
              onClick={() => openUser(item)}
              {...bounceTap(0.03)}
              className="flex w-full items-center gap-3 rounded-full px-2.5 py-2 text-left transition-colors enabled:hover:bg-white/[0.04]"
            >
              <span
                className="flex size-8 shrink-0 items-center justify-center rounded-full bg-white/[0.06] text-[12px] font-bold text-foreground"
              >
                {item.user?.name ? initials(item.user.name) : "?"}
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-[13px] font-medium leading-tight text-foreground/90">
                  {item.user?.name || t("referrals.dialog.deletedUser")}
                </p>
                <p className="truncate text-[11.5px] leading-tight text-muted-foreground">{subtitle(item)}</p>
              </div>
              <Badge tone={item.level === 1 ? "accent" : "neutral"}>
                {t("referrals.list.levelBadge", { level: item.level })}
              </Badge>
              <span className="flex w-24 shrink-0 flex-col items-end text-[12.5px] leading-tight tabular-nums">
                {rewards.length === 0 && <span className="text-muted-foreground">{t("referrals.stats.none")}</span>}
                {rewards.map((reward) => (
                  <span key={reward} className="max-w-full truncate font-semibold text-foreground">
                    {reward}
                  </span>
                ))}
              </span>
            </motion.button>
          );
        })}
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
