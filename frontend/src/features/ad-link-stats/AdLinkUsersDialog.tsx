import { ChevronDown, Loader2, Users, X } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  type AdLink,
  type AttributedUser,
  DEFAULT_PAGE_SIZE,
  listAdLinkAttributedUsers,
} from "@entities/advertising/api";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { Modal, useModalClose } from "@shared/ui/Modal";

interface AdLinkUsersDialogProps {
  adLink: AdLink;
  onClose: () => void;
}

type UsersState =
  | { kind: "loading" }
  | { kind: "error" }
  | { kind: "ready"; items: AttributedUser[]; total: number };

export function AdLinkUsersDialog({ adLink, onClose }: AdLinkUsersDialogProps) {
  return (
    <Modal onClose={onClose} size="lg" scrollable>
      <AdLinkUsersDialogBody adLink={adLink} />
    </Modal>
  );
}

function AdLinkUsersDialogBody({ adLink }: Pick<AdLinkUsersDialogProps, "adLink">) {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const close = useModalClose();
  const [usersState, setUsersState] = useState<UsersState>({ kind: "loading" });
  const [page, setPage] = useState(1);
  const [isLoadingMore, setIsLoadingMore] = useState(false);

  useEffect(() => {
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
  }, [adLink.id]);

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
            <Users className="size-4" />
          </div>
          <span className="truncate">{t("advertising.stats.usersTitle")} · {adLink.name}</span>
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

      <div className="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto px-5 pb-5 pt-4">
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
    </>
  );
}
