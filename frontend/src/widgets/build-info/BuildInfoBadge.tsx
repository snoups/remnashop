import { ArrowUpCircle, Check, Clock, Copy, GitBranch, GitCommit, Info, Star } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { copyToClipboard } from "@shared/lib/clipboard";
import { formatDateTime } from "@shared/lib/relative-time";
import { getSystemMetadata, type SystemMetadata } from "@shared/api/system";
import { bounceTap } from "@shared/lib/bounceState";
import { toggleDebugBar, useDebugState } from "@shared/lib/debug-bar";
import { githubApiUrl, isHttpsUrl, TELEGRAM_URL } from "@shared/lib/external-links";
import { isNewerVersion } from "@shared/lib/version-compare";
import { GithubIcon, TelegramIcon } from "@shared/ui/BrandIcons";
import { BounceIcon } from "@shared/ui/BounceIcon";
import { InfoRow } from "@shared/ui/InfoRow";
import { DialogHeader } from "@shared/ui/DialogHeader";
import { useDialogFocus } from "@shared/ui/modal-hooks";
import { Tag } from "@shared/ui/Tag";
import { LABEL_CLASSNAME, SIDEBAR_PILL_CLASSNAME } from "@widgets/sidebar/nav-pill";
import { IconButton } from "@shared/ui/IconButton";
import { EYEBROW_CLASS } from "@shared/ui/classes";

interface GithubRelease {
  tag_name: string;
  html_url: string;
}

const LONG_PRESS_MS = 600;

const footerLinkClassName =
  "flex flex-1 items-center justify-center gap-2 rounded-full border border-border h-9 px-3 text-sm font-medium text-muted-foreground transition-colors hover:border-glass-border hover:bg-white/[0.06] hover:text-primary";

export function BuildInfoBadge() {
  const { t, i18n } = useTranslation();
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

        // only a CI build can be compared against releases
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
    void copyToClipboard(sha).then((copied) => {
      if (!copied) return;
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 1500);
    });
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
        className={SIDEBAR_PILL_CLASSNAME}
        initial="rest"
        whileHover="hover"
        {...bounceTap()}
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
              tabIndex={-1}
              className="absolute inset-0 cursor-default"
              onClick={() => setIsOpen(false)}
            />

            <BuildInfoPanel onEscape={() => setIsOpen(false)}>
            <DialogHeader
              icon={Info}
              title={t("buildInfo.title")}
              onClose={() => setIsOpen(false)}
            />

            <div className="flex flex-col gap-3 px-5 pb-5 pt-4">
              <div className="flex items-center justify-between rounded-2xl border border-white/[0.08] bg-white/[0.03] px-4 py-3.5">
                <div>
                  <div className={EYEBROW_CLASS}>
                    {t("buildInfo.version")}
                  </div>
                  <div className="mt-0.5 font-mono text-lg font-bold text-foreground">v{currentVersion}</div>
                </div>

                {isUpdateAvailable && release && isHttpsUrl(release.html_url) && (
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
                  <InfoRow icon={GitBranch} label={t("buildInfo.branch")} mono>
                    {metadata.git.branch}
                  </InfoRow>
                )}

                {isOfficialBuild && metadata.git.commit_sha && (
                  <InfoRow icon={GitCommit} label={t("buildInfo.commit")} mono>
                    <a
                      href={`${metadata.repository_url}/commit/${metadata.git.commit_sha}`}
                      target="_blank"
                      rel="noreferrer"
                      className="hover:text-primary"
                    >
                      {metadata.git.commit_sha.slice(0, 7)}
                    </a>
                    <IconButton size="6"
                      onClick={handleCopyCommit}
                    >
                      {isCopied ? (
                        <Check className="size-3.5 text-success" />
                      ) : (
                        <Copy className="size-3.5" />
                      )}
                    </IconButton>
                  </InfoRow>
                )}

                {isOfficialBuild && metadata.git.commit_sha && metadata.git.commit_date && (
                  <InfoRow icon={Clock} label={t("buildInfo.commitDate")} mono>
                    {formatDateTime(metadata.git.commit_date, i18n.language)}
                  </InfoRow>
                )}
              </div>

              <div className="flex gap-2">
                <motion.a
                  href={TELEGRAM_URL}
                  target="_blank"
                  rel="noreferrer"
                  {...bounceTap()}
                  className={footerLinkClassName}
                >
                  <TelegramIcon className="size-4" />
                  {t("buildInfo.telegramButton")}
                </motion.a>
                <motion.a
                  href={metadata.repository_url}
                  target="_blank"
                  rel="noreferrer"
                  {...bounceTap()}
                  className={footerLinkClassName}
                >
                  <GithubIcon className="size-4" />
                  {t("buildInfo.githubButton")}
                  {stars !== null && (
                    <Tag>
                      <Star className="size-2.5" />
                      {stars}
                    </Tag>
                  )}
                </motion.a>
              </div>
            </div>
            </BuildInfoPanel>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}

// Own overlay and animation on purpose (not Modal), but the same keyboard and a11y behaviour as one:
// mounted only while open, so useDialogFocus runs on open and restores focus on close.
function BuildInfoPanel({ onEscape, children }: { onEscape: () => void; children: ReactNode }) {
  const panelRef = useRef<HTMLDivElement>(null);
  useDialogFocus(panelRef, onEscape);

  return (
    <motion.div
      ref={panelRef}
      data-dialog
      tabIndex={-1}
      initial={{ opacity: 0, scale: 0.94, y: 8 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.94, y: 8 }}
      transition={{ duration: 0.18, ease: "easeOut" }}
      className="relative z-50 w-full max-w-sm rounded-dialog border border-white/[0.14] bg-popover/60 shadow-[0_24px_48px_-20px_rgba(4,8,20,0.6),inset_0_1px_0_rgba(232,236,251,0.16)] outline-none backdrop-blur-2xl backdrop-saturate-150"
    >
      {children}
    </motion.div>
  );
}
