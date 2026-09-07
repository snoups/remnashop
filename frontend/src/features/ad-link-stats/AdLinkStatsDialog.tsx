import { AlertCircle, BarChart3, ChevronDown, Loader2, X } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  type AdLink,
  type AttributedUser,
  DEFAULT_PAGE_SIZE,
  getAdLinkStats,
  listAdLinkAttributedUsers,
} from "@entities/advertising/api";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { Modal, useModalClose } from "@shared/ui/Modal";

interface AdLinkStatsDialogProps {
  adLink: AdLink;
  canViewUsers: boolean;
  onClose: () => void;
}

function StatCell({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5 rounded-xl border border-border bg-white/[0.03] px-3 py-2.5">
      <span className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">{label}</span>
      <span className="text-[15px] font-bold text-foreground">{value}</span>
    </div>
  );
}

type UsersState =
  | { kind: "loading" }
  | { kind: "error" }
  | { kind: "ready"; items: AttributedUser[]; total: number };

export function AdLinkStatsDialog({ adLink, canViewUsers, onClose }: AdLinkStatsDialogProps) {
  return (
    <Modal onClose={onClose} size="lg" scrollable>
      <AdLinkStatsDialogBody adLink={adLink} canViewUsers={canViewUsers} />
    </Modal>
  );
}

function AdLinkStatsDialogBody({
  adLink,
  canViewUsers,
}: Pick<AdLinkStatsDialogProps, "adLink" | "canViewUsers">) {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const close = useModalClose();
  const [statsState] = useAsyncResource((signal) => getAdLinkStats(adLink.id, signal));
  const [usersState, setUsersState] = useState<UsersState>({ kind: "loading" });
  const [page, setPage] = useState(1);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const none = t("advertising.stats.none");

  useEffect(() => {
    if (!canViewUsers) return;
    const controller = new AbortController();
    setPage(1);
    listAdLinkAttributedUsers(adLink.id, 1, DEFAULT_PAGE_SIZE, controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) setUsersState({ kind: "ready", items: result.items, total: result.total });
      })
      .catch(() => {
        if (!controller.signal.aborted) setUsersState({ kind: "error" });
      });
    return () => controller.abort();
  }, [adLink.id, canViewUsers]);

  const handleLoadMore = async () => {
    const nextPage = page + 1;
    setIsLoadingMore(true);
    try {
      const result = await listAdLinkAttributedUsers(adLink.id, nextPage, DEFAULT_PAGE_SIZE);
      setUsersState((prev) =>
        prev.kind === "ready"
          ? { kind: "ready", items: [...prev.items, ...result.items], total: result.total }
          : prev,
      );
      setPage(nextPage);
    } catch {
      // keep current items on failure; the load-more button stays available to retry
    } finally {
      setIsLoadingMore(false);
    }
  };

  const hasMore = usersState.kind === "ready" && usersState.items.length < usersState.total;

  return (
    <>
      <div className="flex shrink-0 items-center justify-between border-b border-border px-5 py-4">
        <h2 className="flex items-center gap-2.5 text-base font-bold text-foreground">
          <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] text-foreground backdrop-blur-md">
            <BarChart3 className="size-4" />
          </div>
          <span className="truncate">{adLink.name}</span>
        </h2>
        <button
          type="button"
          onClick={close}
          aria-label={t("advertising.stats.close")}
          className="flex size-8 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-white/[0.06] hover:text-foreground"
        >
          <X className="size-4" />
        </button>
      </div>

      <div className="flex min-h-0 flex-1 flex-col overflow-y-auto px-5 pb-5 pt-4">
        {statsState.kind === "loading" && (
          <div className="flex justify-center py-8 text-muted-foreground">
            <Loader2 className="size-5 animate-spin" />
          </div>
        )}
        {statsState.kind === "error" && (
          <div className="flex flex-col items-center gap-2 py-8 text-error">
            <AlertCircle className="size-5" />
            <p className="text-sm">{t("advertising.stats.loadError")}</p>
          </div>
        )}
        {statsState.kind === "ready" && (
          <div className="grid grid-cols-3 gap-2">
            <StatCell label={t("advertising.stats.attributions")} value={String(statsState.data.attributions_count)} />
            <StatCell label={t("advertising.stats.paidCount")} value={String(statsState.data.paid_count)} />
            <StatCell label={t("advertising.stats.conversionRate")} value={`${statsState.data.conversion_rate}%`} />
            <StatCell
              label={t("advertising.stats.revenue")}
              value={
                Object.entries(statsState.data.revenue_by_currency)
                  .map(([currency, amount]) => `${amount} ${currency}`)
                  .join(", ") || none
              }
            />
            <StatCell
              label={t("advertising.stats.cost")}
              value={`${statsState.data.cost} ${statsState.data.report_currency}`}
            />
            <StatCell label={t("advertising.stats.cpa")} value={statsState.data.cpa ?? none} />
            <StatCell
              label={t("advertising.stats.roi")}
              value={statsState.data.roi !== null ? `${statsState.data.roi}%` : none}
            />
          </div>
        )}

        {canViewUsers && (
          <div className="mt-5 flex flex-col gap-2 border-t border-border pt-4">
            <span className="text-[12px] font-semibold uppercase tracking-wide text-muted-foreground">
              {t("advertising.stats.usersTitle")}
            </span>
            {usersState.kind === "loading" && (
              <div className="flex justify-center py-4 text-muted-foreground">
                <Loader2 className="size-4 animate-spin" />
              </div>
            )}
            {usersState.kind === "error" && (
              <p className="py-2 text-[12.5px] text-error">{t("advertising.stats.loadError")}</p>
            )}
            {usersState.kind === "ready" && usersState.items.length === 0 && (
              <p className="py-2 text-[12.5px] text-muted-foreground">{t("advertising.stats.usersEmpty")}</p>
            )}
            {usersState.kind === "ready" && usersState.items.length > 0 && (
              <>
                <div className="flex flex-col divide-y divide-border/50">
                  {usersState.items.map((user) => (
                    <div key={user.user_id} className="flex items-center justify-between gap-3 py-2">
                      <div className="min-w-0">
                        <p className="truncate text-[13px] font-medium text-foreground">{user.name}</p>
                        <p className="text-[11.5px] text-muted-foreground">
                          {t(`advertising.channel.${user.channel}`)} &middot;{" "}
                          {new Date(user.created_at).toLocaleDateString()}
                        </p>
                      </div>
                      <span
                        className={`shrink-0 rounded-full border px-2 py-0.5 text-[10.5px] font-semibold uppercase tracking-wide ${
                          user.has_paid
                            ? "border-success/30 bg-success/10 text-success"
                            : "border-border bg-white/[0.04] text-muted-foreground"
                        }`}
                      >
                        {user.has_paid ? t("advertising.stats.hasPaid") : t("advertising.stats.notPaid")}
                      </span>
                    </div>
                  ))}
                </div>
                {hasMore && (
                  <div className="flex justify-center pt-2">
                    <motion.button
                      type="button"
                      onClick={() => void handleLoadMore()}
                      disabled={isLoadingMore}
                      aria-label={isLoadingMore ? t("advertising.stats.loadingMore") : undefined}
                      {...bounceTap(bounceStrength)}
                      className="flex items-center gap-1.5 rounded-full border border-border px-3.5 py-1.5 text-[12.5px] text-foreground/90 transition-colors hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {isLoadingMore ? (
                        <Loader2 className="size-3.5 animate-spin" />
                      ) : (
                        <ChevronDown className="size-3.5" />
                      )}
                      {!isLoadingMore && t("advertising.stats.loadMore")}
                    </motion.button>
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </div>
    </>
  );
}
