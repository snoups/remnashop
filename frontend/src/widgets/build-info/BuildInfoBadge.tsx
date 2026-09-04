import { ArrowUpCircle, Check, Clock, Copy, GitBranch, GitCommit, Info, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import type { SystemMetadata } from "@shared/api/system";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { githubApiUrl, TELEGRAM_URL } from "@shared/lib/external-links";
import { isNewerVersion } from "@shared/lib/version-compare";
import { GithubIcon, TelegramIcon } from "@shared/ui/BrandIcons";
import { InfoRow } from "@shared/ui/InfoRow";

interface GithubRelease {
  tag_name: string;
  html_url: string;
}

interface BuildInfoBadgeProps {
  /** Fetched by the parent (ExternalLinksRow), which renders this alongside
   * its own GitHub-star link off the same metadata -- fetching it again here
   * would double the /system/metadata request on every sidebar mount. */
  metadata: SystemMetadata | null;
}

export function BuildInfoBadge({ metadata }: BuildInfoBadgeProps) {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const [isOpen, setIsOpen] = useState(false);
  const [latestRelease, setLatestRelease] = useState<GithubRelease | null>(null);
  const [isCopied, setIsCopied] = useState(false);

  const isOfficialBuild = metadata?.git.is_official_build ?? false;

  const handleOpen = () => {
    setIsOpen(true);
    // Only a real CI-built artifact is comparable against releases — skip for dev/local runs.
    if (!metadata || !isOfficialBuild || latestRelease) return;

    fetch(githubApiUrl(metadata.repository_url, "/releases/latest"))
      .then((response) => (response.ok ? (response.json() as Promise<GithubRelease>) : null))
      .then((release) => setLatestRelease(release))
      .catch(() => setLatestRelease(null));
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
  const isUpdateAvailable = latestRelease ? isNewerVersion(latestRelease.tag_name, currentVersion) : false;

  return (
    <>
      <motion.button
        type="button"
        onClick={handleOpen}
        aria-label={t("buildInfo.title")}
        title={t("buildInfo.title")}
        className="flex basis-[calc(50%-2px)] items-center justify-center gap-1.5 rounded-full py-2.5 text-muted-foreground transition-colors hover:bg-white/[0.06] hover:text-foreground"
        {...bounceTap(bounceStrength)}
      >
        <Info className="size-5" fill="currentColor" stroke="var(--color-canvas)" />
        <span className="font-mono text-[11px] font-medium">{currentVersion}</span>
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

                {isUpdateAvailable && latestRelease && (
                  <a
                    href={latestRelease.html_url}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center gap-1.5 rounded-full border border-primary/40 bg-accent px-3 py-1.5 text-[12px] font-semibold text-primary transition-colors hover:bg-primary/20"
                  >
                    <ArrowUpCircle className="size-3.5" />
                    {latestRelease.tag_name}
                  </a>
                )}
              </div>

              <div className="flex flex-col">
                {isOfficialBuild && metadata.git.branch && (
                  <InfoRow icon={GitBranch} label={t("buildInfo.branch")}>
                    {metadata.git.branch}
                  </InfoRow>
                )}

                {isOfficialBuild && metadata.git.commit_sha ? (
                  <InfoRow icon={GitCommit} label={t("buildInfo.commit")}>
                    <a
                      href={`${metadata.repository_url}/commit/${metadata.git.commit_sha}`}
                      target="_blank"
                      rel="noreferrer"
                      title={metadata.git.commit_sha}
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
                ) : (
                  <InfoRow icon={GitCommit} label={t("buildInfo.commit")}>
                    <span className="font-sans font-medium text-muted-foreground">{t("buildInfo.localBuild")}</span>
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
                  className="flex flex-1 items-center justify-center gap-2 rounded-full border border-border px-3 py-2 text-sm font-medium text-primary transition-colors hover:bg-white/[0.06]"
                >
                  <TelegramIcon className="size-4" />
                  {t("buildInfo.telegramButton")}
                </motion.a>
                <motion.a
                  href={metadata.repository_url}
                  target="_blank"
                  rel="noreferrer"
                  {...bounceTap(bounceStrength)}
                  className="flex flex-1 items-center justify-center gap-2 rounded-full border border-border px-3 py-2 text-sm font-medium text-primary transition-colors hover:bg-white/[0.06]"
                >
                  <GithubIcon className="size-4" />
                  {t("buildInfo.githubButton")}
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
