import { Crown, PiggyBank, Star, Wallet, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { getSystemMetadata, type SystemMetadata } from "@shared/api/system";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { BOOSTY_URL, COMMUNITY_URL, githubApiUrl, TELEGRAM_URL, YOOKASSA_URL } from "@shared/lib/external-links";
import { GithubIcon, TelegramIcon } from "@shared/ui/BrandIcons";
import { BuildInfoBadge } from "@widgets/build-info/BuildInfoBadge";

const iconButtonClassName =
  "flex basis-[calc(50%-2px)] items-center justify-center rounded-full py-2.5 text-muted-foreground transition-colors hover:bg-white/[0.06] hover:text-foreground";

export function ExternalLinksRow() {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const [metadata, setMetadata] = useState<SystemMetadata | null>(null);
  const [stars, setStars] = useState<number | null>(null);
  const [isDonateOpen, setIsDonateOpen] = useState(false);

  // Fetched once here and handed down to BuildInfoBadge as a prop, rather
  // than each fetching it independently -- both mount together, so two
  // independent effects meant two /system/metadata requests every time.
  useEffect(() => {
    const controller = new AbortController();

    getSystemMetadata(controller.signal)
      .then((data) => {
        if (controller.signal.aborted) return;
        setMetadata(data);
        return fetch(githubApiUrl(data.repository_url), { signal: controller.signal })
          .then((response) => (response.ok ? (response.json() as Promise<{ stargazers_count: number }>) : null))
          .then((repo) => {
            if (!controller.signal.aborted && repo) setStars(repo.stargazers_count);
          });
      })
      .catch(() => {});

    return () => controller.abort();
  }, []);

  const tapProps = bounceTap(bounceStrength, 0.12);

  return (
    <>
      {metadata && (
        <motion.a
          href={metadata.repository_url}
          target="_blank"
          rel="noreferrer"
          aria-label={t("buildInfo.githubButton")}
          title={t("buildInfo.githubButton")}
          className={`${iconButtonClassName} gap-2.5`}
          {...tapProps}
        >
          <GithubIcon className="size-4" />
          {stars !== null && (
            <span className="flex items-center gap-0.5 text-[11px] font-medium">
              <Star className="size-3" />
              {stars}
            </span>
          )}
        </motion.a>
      )}

      <BuildInfoBadge metadata={metadata} />

      <motion.button
        type="button"
        onClick={() => setIsDonateOpen(true)}
        aria-label={t("donate.button")}
        title={t("donate.button")}
        className={iconButtonClassName}
        {...tapProps}
      >
        <Crown className="size-4" fill="currentColor" />
      </motion.button>

      <motion.a
        href={TELEGRAM_URL}
        target="_blank"
        rel="noreferrer"
        aria-label={t("buildInfo.telegramButton")}
        title={t("buildInfo.telegramButton")}
        className={iconButtonClassName}
        {...tapProps}
      >
        <TelegramIcon className="size-4" />
      </motion.a>

      <AnimatePresence>
        {isDonateOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15, ease: "easeOut" }}
            className="fixed inset-0 z-40 flex items-center justify-center bg-black/55 backdrop-blur-3xl p-4"
          >
            <button
              type="button"
              aria-hidden
              tabIndex={-1}
              className="absolute inset-0 cursor-default"
              onClick={() => setIsDonateOpen(false)}
            />

            <motion.div
              initial={{ opacity: 0, scale: 0.94, y: 8 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.94, y: 8 }}
              transition={{ duration: 0.18, ease: "easeOut" }}
              className="relative z-50 w-full max-w-sm rounded-dialog border border-white/[0.14] bg-popover/60 shadow-[0_24px_48px_-20px_rgba(4,8,20,0.6),inset_0_1px_0_rgba(232,236,251,0.16)] backdrop-blur-2xl backdrop-saturate-150"
            >
              <div className="flex items-center justify-between border-b border-border px-5 py-4">
                <h2 className="flex items-center gap-2.5 text-base font-bold text-foreground">
                  <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] text-foreground backdrop-blur-md">
                    <Crown className="size-4" />
                  </div>
                  {t("donate.title")}
                </h2>
                <button
                  type="button"
                  onClick={() => setIsDonateOpen(false)}
                  aria-label={t("profile.edit.close")}
                  className="flex size-8 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-white/[0.06] hover:text-foreground"
                >
                  <X className="size-4" />
                </button>
              </div>

              <div className="flex flex-col gap-3 px-5 pb-5 pt-4">
                <p className="text-[12.5px] text-muted-foreground">{t("donate.description")}</p>

                <div className="flex gap-2">
                  <motion.a
                    href={BOOSTY_URL}
                    target="_blank"
                    rel="noreferrer"
                    {...tapProps}
                    className="flex flex-1 items-center justify-center gap-2 rounded-full border border-border px-3 py-2 text-sm font-medium text-primary transition-colors hover:bg-white/[0.06]"
                  >
                    <PiggyBank className="size-4" />
                    {t("donate.boostyLabel")}
                  </motion.a>
                  <motion.a
                    href={YOOKASSA_URL}
                    target="_blank"
                    rel="noreferrer"
                    {...tapProps}
                    className="flex flex-1 items-center justify-center gap-2 rounded-full border border-border px-3 py-2 text-sm font-medium text-primary transition-colors hover:bg-white/[0.06]"
                  >
                    <Wallet className="size-4" />
                    {t("donate.yookassaLabel")}
                  </motion.a>
                </div>

                <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-4">
                  <div className="text-[13px] font-semibold text-foreground">{t("donate.communityTitle")}</div>
                  <p className="mt-1 text-[12.5px] text-muted-foreground">{t("donate.communityDescription")}</p>
                  <motion.a
                    href={COMMUNITY_URL}
                    target="_blank"
                    rel="noreferrer"
                    {...tapProps}
                    className="mt-3 flex items-center justify-center gap-2 rounded-full bg-accent px-3 py-2 text-sm font-medium text-primary transition-colors hover:bg-primary/20"
                  >
                    {t("donate.communityButton")}
                  </motion.a>
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
