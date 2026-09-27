import { ArrowUpCircle, Check, Clock, Copy, GitBranch, GitCommit, Info, Star, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { getSystemMetadata, type SystemMetadata } from "@shared/api/system";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { toggleDebugBar, useDebugState } from "@shared/lib/debug-bar";
import { githubApiUrl, TELEGRAM_URL } from "@shared/lib/external-links";
import { isNewerVersion } from "@shared/lib/version-compare";
import { GithubIcon, TelegramIcon } from "@shared/ui/BrandIcons";
import { BounceIcon } from "@shared/ui/BounceIcon";
import { InfoRow } from "@shared/ui/InfoRow";
import { LABEL_CLASSNAME, SIDEBAR_PILL_CLASSNAME } from "@widgets/sidebar/nav-pill";

interface GithubRelease {
  tag_name: string;
  html_url: string;
}

const LONG_PRESS_MS = 600;

const footerLinkClassName =
  "flex flex-1 items-center justify-center gap-2 rounded-full border border-border px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:border-glass-border hover:bg-white/[0.06] hover:text-primary";

export function BuildInfoBadge() {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const { fakeUpdate } = useDebugState();
  const [metadata, setMetadata] = useState<SystemMetadata | null>(null);
  const [stars, setStars] = useState<number | null>(null);
  const [isOpen, setIsOpen] = useState(false);
  const [latestRelease, setLatestRelease] = useState<GithubRelease | null>(null);
  const [isCopied, setIsCopied] = useState(false);
  const longPressTimer = useRef<number | null>(null);
  const didLongPress = useRef(false);

  useEffect(() => {
    const controller = new AbortController();

    getSystemMetadata(controller.signal)
      .then((data) => {
        if (controller.signal.aborted) return;
        setMetadata(data);

        fetch(githubApiUrl(data.repository_url), { signal: controller.signal })
          .then((response) => (response.ok ? (response.json() as Promise<{ stargazers_count: number }>) : null))
          .then((repo) => {
            if (!controller.signal.aborted && repo) setStars(repo.stargazers_count);
          })
          .catch(() => {});

        // Only a real CI-built artifact is comparable against releases — skip for dev/local runs.
        if (!data.git.is_official_build) return;

        fetch(githubApiUrl(data.repository_url, "/releases/latest"), { signal: controller.signal })
          .then((response) => (response.ok ? (response.json() as Promise<GithubRelease>) : null))
          .then((release) => {
            if (!controller.signal.aborted) setLatestRelease(release);
          })
          .catch(() => {});
      })
      .catch(() => {});

    return () => controller.abort();
  }, []);

  const isOfficialBuild = metadata?.git.is_official_build ?? false;

  const startLongPress = () => {
    didLongPress.current = false;
    longPressTimer.current = window.setTimeout(() => {
      didLongPress.current = true;
      toggleDebugBar();
    }, LONG_PRESS_MS);
  };

  const cancelLongPress = () => {
    if (longPressTimer.current !== null) clearTimeout(longPressTimer.current);
    longPressTimer.current = null;
  };

  const handleOpen = () => {
    cancelLongPress();
    // Keyboard activation never fires pointerdown, so clear the flag here too.
    if (didLongPress.current) {
      didLongPress.current = false;
      return;
    }
    setIsOpen(true);
  };

  const handleCopyCommit = () => {
    const sha = metadata?.git.commit_sha;
    if (!sha) return;
    if (navigator.clipboard) {
      navigator.clipboard.writeText(sha).catch(() => {});
    }
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 1500);
  };

  if (!metadata) return null;

  const currentVersion = metadata.version;
  const release = fakeUpdate
    ? { tag_name: "v999.0.0", html_url: `${metadata.repository_url}/releases` }
    : latestRelease;
  const isUpdateAvailable = release ? isNewerVersion(release.tag_name, currentVersion) : false;

  return (
    <>
      <motion.button
        type="button"
        onClick={handleOpen}
        onPointerDown={startLongPress}
        onPointerUp={cancelLongPress}
        onPointerLeave={cancelLongPress}
        onContextMenu={(event) => event.preventDefault()}
        aria-label={t("buildInfo.title")}
        className={SIDEBAR_PILL_CLASSNAME}
        initial="rest"
        whileHover="hover"
        {...bounceTap(bounceStrength)}
      >
        <BounceIcon icon={Info} size={17} hoverSize={23.5} />
        <span className={`${LABEL_CLASSNAME} font-mono`}>{currentVersion}</span>
        {isUpdateAvailable && release && (
          <span
            className={`${LABEL_CLASSNAME} ml-auto rounded-full border border-primary/40 bg-accent px-2 py-1 font-mono text-[10px] font-semibold leading-none text-primary`}
          >
            {release.tag_name}
          </span>
        )}
      </motion.button>

      <AnimatePresence>
        {isOpen && (
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
              onClick={() => setIsOpen(false)}
            />

            <motion.div
              initial={{ opacity: 0, scale: 0.94, y: 8 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.94, y: 8 }}
              transition={{ duration: 0.18, ease: "easeOut" }}
              className="relative z-50 w-full max-w-sm rounded-dialog border border-white/[0.14] bg-popover/60 shadow-[0_24px_48px_-20px_rgba(4,8,20,0.6),inset_0_1px_0_rgba(232,236,251,0.16)] backdrop-blur-2xl backdrop-saturate-150">
            <div className="flex items-center justify-between border-b border-border px-5 py-4">
              <h2 className="flex items-center gap-2.5 text-base font-bold text-foreground">
                <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] text-foreground backdrop-blur-md">
                  <Info className="size-4" />
                </div>
                {t("buildInfo.title")}
              </h2>
              <button
                type="button"
                onClick={() => setIsOpen(false)}
                aria-label={t("buildInfo.close")}
                className="flex size-8 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-white/[0.06] hover:text-foreground"
              >
                <X className="size-4" />
              </button>
            </div>

            <div className="flex flex-col gap-3 px-5 pb-5 pt-4">
              <div className="flex items-center justify-between rounded-2xl border border-white/[0.08] bg-white/[0.03] px-4 py-3.5">
                <div>
                  <div className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                    {t("buildInfo.version")}
                  </div>
                  <div className="mt-0.5 font-mono text-lg font-bold text-foreground">v{currentVersion}</div>
                </div>

                {isUpdateAvailable && release && (
                  <a
                    href={release.html_url}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center gap-1.5 rounded-full border border-primary/40 bg-accent px-3 py-1.5 font-mono text-[12px] font-semibold text-primary transition-colors hover:bg-primary/20"
                  >
                    <ArrowUpCircle className="size-3.5" />
                    {release.tag_name}
                  </a>
                )}
              </div>

              <div className="flex flex-col">
                {isOfficialBuild && metadata.git.branch && (
                  <InfoRow icon={GitBranch} label={t("buildInfo.branch")}>
                    {metadata.git.branch}
                  </InfoRow>
                )}

                {isOfficialBuild && metadata.git.commit_sha && (
                  <InfoRow icon={GitCommit} label={t("buildInfo.commit")}>
                    <a
                      href={`${metadata.repository_url}/commit/${metadata.git.commit_sha}`}
                      target="_blank"
                      rel="noreferrer"
                      className="hover:text-primary"
                    >
                      {metadata.git.commit_sha.slice(0, 7)}
                    </a>
                    <button
                      type="button"
                      onClick={handleCopyCommit}
                      aria-label={t("buildInfo.copyCommit")}
                      className="flex size-6 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-white/[0.08] hover:text-foreground"
                    >
                      {isCopied ? (
                        <Check className="size-3.5 text-success" />
                      ) : (
                        <Copy className="size-3.5" />
                      )}
                    </button>
                  </InfoRow>
                )}

                {isOfficialBuild && metadata.git.commit_sha && metadata.git.commit_date && (
                  <InfoRow icon={Clock} label={t("buildInfo.commitDate")}>
                    <span className="font-sans font-medium text-foreground">
                      {new Date(metadata.git.commit_date).toLocaleString()}
                    </span>
                  </InfoRow>
                )}
              </div>

              <div className="flex gap-2">
                <motion.a
                  href={TELEGRAM_URL}
                  target="_blank"
                  rel="noreferrer"
                  {...bounceTap(bounceStrength)}
                  className={footerLinkClassName}
                >
                  <TelegramIcon className="size-4" />
                  {t("buildInfo.telegramButton")}
                </motion.a>
                <motion.a
                  href={metadata.repository_url}
                  target="_blank"
                  rel="noreferrer"
                  {...bounceTap(bounceStrength)}
                  className={footerLinkClassName}
                >
                  <GithubIcon className="size-4" />
                  {t("buildInfo.githubButton")}
                  {stars !== null && (
                    <span className="flex items-center gap-0.5 rounded-full bg-white/[0.06] px-1.5 py-0.5 text-[11px] font-semibold text-foreground">
                      <Star className="size-2.5" />
                      {stars}
                    </span>
                  )}
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
