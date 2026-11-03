import { createPortal } from "react-dom";
import { ArrowUpCircle, Clock, ExternalLink, GitBranch, GitCommit, Info, Star } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { formatDateTime } from "@shared/lib/relative-time";
import { getSystemMetadata, type SystemMetadata } from "@shared/api/system";
import { toggleDebugBar, useDebugState } from "@shared/lib/debug-bar";
import { githubApiUrl, isHttpsUrl, TELEGRAM_URL } from "@shared/lib/external-links";
import { isNewerVersion } from "@shared/lib/version-compare";
import { GithubIcon, TelegramIcon } from "@shared/ui/BrandIcons";
import { InfoRow } from "@shared/ui/InfoRow";
import { DialogHeader } from "@shared/ui/glass/DialogHeader";
import { ModalCloseContext, useDialogFocus } from "@shared/ui/modal-hooks";
import { Tag } from "@shared/ui/Tag";
import { LABEL_CLASSNAME, SIDEBAR_PILL_CLASSNAME } from "@widgets/sidebar/nav-pill";
import { GLASS_DIALOG_CARD_CLASS, GLASS_DIALOG_CLASS, GLASS_LINK_BUTTON_CLASS } from "@shared/ui/classes";
import { Pressable } from "@shared/ui/Pressable";

interface GithubRelease {
  tag_name: string;
  html_url: string;
}

const LONG_PRESS_MS = 600;
// the debug bar's preview of a CI image; local builds carry no git data
const FAKE_OFFICIAL_GIT = {
  commit_sha: "4409409c5a7e1f3b8d2c6e0a9f4b7d1c3e5a8f20",
  commit_date: "2026-11-03T09:30:00Z",
  branch: "main",
  is_official_build: true,
};

export function BuildInfoBadge({ mobile = false }: { mobile?: boolean }) {
  const labelClass = mobile ? "truncate" : LABEL_CLASSNAME;
  const renderOverlay = (content: ReactNode) => mobile ? createPortal(content, document.body) : content;
  const { t, i18n } = useTranslation();
  const { fakeUpdate, fakeOfficialBuild } = useDebugState();
  const [metadata, setMetadata] = useState<SystemMetadata | null>(null);
  const [stars, setStars] = useState<number | null>(null);
  const [isOpen, setIsOpen] = useState(false);
  const [latestRelease, setLatestRelease] = useState<GithubRelease | null>(null);
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

  if (!metadata) return null;

  const git = fakeOfficialBuild ? FAKE_OFFICIAL_GIT : metadata.git;
  const currentVersion = metadata.version;
  const release = fakeUpdate
    ? { tag_name: "v999.0.0", html_url: `${metadata.repository_url}/releases` }
    : latestRelease;
  const isUpdateAvailable = release ? isNewerVersion(release.tag_name, currentVersion) : false;

  return (
    <>
      <Pressable
        type="button"
        onClick={handleOpen}
        onPointerDown={mobile ? undefined : startLongPress}
        onPointerUp={cancelLongPress}
        onPointerLeave={cancelLongPress}
        onContextMenu={(event) => event.preventDefault()}
        className={mobile ? "flex h-11 min-w-0 flex-1 items-center justify-center gap-3 rounded-full border border-glass-border bg-white/[0.05] px-4 text-[13px] font-medium text-muted-foreground hover:bg-white/[0.07] hover:text-foreground" : SIDEBAR_PILL_CLASSNAME}
      >
        {mobile ? <Info className="size-5 shrink-0" /> : <Info className="size-4 shrink-0" />}
        <span className={`${labelClass} font-mono`}>{currentVersion}</span>
        {!mobile && isUpdateAvailable && release && (
          <span
            className={`${labelClass} ml-auto rounded-full border border-primary/40 bg-accent px-2 py-1 font-mono text-[10px] font-semibold leading-none text-primary shadow-[0_0_10px_color-mix(in_srgb,var(--color-primary)_40%,transparent)]`}
          >
            {release.tag_name}
          </span>
        )}
      </Pressable>

      {renderOverlay(<AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15, ease: "easeOut" }}
            className={`fixed inset-0 ${mobile ? "z-[60]" : "z-40"} flex items-center justify-center bg-black/55 backdrop-blur-3xl p-4`}
          >
            <button
              type="button"
              tabIndex={-1}
              className="absolute inset-0 cursor-default"
              onClick={() => setIsOpen(false)}
            />

            <BuildInfoPanel onEscape={() => setIsOpen(false)}>
            <DialogHeader icon={Info} title={t("buildInfo.title")} />

            <div className="flex flex-col gap-3 p-3 [--dialog-pad:0.75rem]">
              <div className={GLASS_DIALOG_CARD_CLASS}>
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="text-[12px] text-muted-foreground">{t("buildInfo.version")}</div>
                    <div className="mt-0.5 font-mono text-[15px] font-semibold text-foreground">v{currentVersion}</div>
                  </div>

                  {isUpdateAvailable && release && isHttpsUrl(release.html_url) && (
                    <a
                      href={release.html_url}
                      target="_blank"
                      rel="noreferrer"
                      className="flex h-8 items-center gap-1.5 rounded-full border border-primary/35 bg-primary/15 px-3 font-mono text-[12px] font-medium text-primary transition-colors hover:bg-primary/20"
                    >
                      <ArrowUpCircle className="size-3.5" />
                      {release.tag_name}
                    </a>
                  )}
                </div>
              </div>

              {git.is_official_build && (git.branch || git.commit_sha) && (
                <div className="flex flex-col rounded-xl border border-white/[0.08] bg-white/[0.03] px-1 py-1.5">
                {git.branch && (
                  <InfoRow icon={GitBranch} label={t("buildInfo.branch")} copyValue={git.branch} mono>
                    {git.branch}
                  </InfoRow>
                )}

                {git.commit_sha && (
                  <InfoRow
                    icon={GitCommit}
                    label={t("buildInfo.commit")}
                    copyValue={git.commit_sha}
                    action={
                      <a
                        href={`${metadata.repository_url}/commit/${git.commit_sha}`}
                        target="_blank"
                        rel="noreferrer"
                        className="text-muted-foreground transition-colors hover:text-primary"
                      >
                        <ExternalLink className="size-3.5" />
                      </a>
                    }
                    mono
                  >
                    {git.commit_sha.slice(0, 7)}
                  </InfoRow>
                )}

                {git.commit_sha && git.commit_date && (
                  <InfoRow
                    icon={Clock}
                    label={t("buildInfo.commitDate")}
                    copyValue={formatDateTime(git.commit_date, i18n.language)}
                    mono
                  >
                    {formatDateTime(git.commit_date, i18n.language)}
                  </InfoRow>
                )}
                </div>
              )}
            </div>

            <div className="flex gap-2 border-t border-white/[0.08] p-4">
              <Pressable as="a" href={TELEGRAM_URL} target="_blank" rel="noreferrer" className={GLASS_LINK_BUTTON_CLASS}>
                <TelegramIcon className="size-4" />
                {t("buildInfo.telegramButton")}
              </Pressable>
              <Pressable as="a" href={metadata.repository_url} target="_blank" rel="noreferrer" className={GLASS_LINK_BUTTON_CLASS}>
                <GithubIcon className="size-4" />
                {t("buildInfo.githubButton")}
                {stars !== null && (
                  <Tag>
                    <Star className="size-2.5" />
                    {stars}
                  </Tag>
                )}
              </Pressable>
            </div>
            </BuildInfoPanel>
          </motion.div>
        )}
      </AnimatePresence>)}
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
      className={`relative z-50 w-full max-w-sm outline-none ${GLASS_DIALOG_CLASS}`}
    >
      <ModalCloseContext.Provider value={onEscape}>{children}</ModalCloseContext.Provider>
    </motion.div>
  );
}
