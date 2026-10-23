import { Bot, ScrollText } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useLayoutEffect, useRef, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { getErrorMessage } from "@shared/api/http";
import {
  getBotLogs,
  getBotSettings,
  getBotStatus,
  removeBotProxy,
  restartBot,
  setBotProxy,
  updateBotSettings,
} from "@entities/settings/api";
import type { BotSettings, BotStatus } from "@entities/settings/api";
import { usePermissions } from "@entities/user/use-current-user";
import { copyToClipboard } from "@shared/lib/clipboard";
import { bounceTap } from "@shared/lib/bounceState";
import { randomString } from "@shared/lib/random-string";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { FieldHint } from "@shared/ui/FieldHint";
import { Modal } from "@shared/ui/Modal";
import { Spinner } from "@shared/ui/Spinner";
import { Switch } from "@shared/ui/Switch";
import { Button } from "@shared/ui/Button";
import { DialogHeader } from "@shared/ui/DialogHeader";
import { CardHeader } from "@shared/ui/CardHeader";

// Telegram's secret_token requirement: 1-256 chars, only A-Z, a-z, 0-9, "_", "-".
const SECRET_TOKEN_CHARSET =
  "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-";
const SECRET_TOKEN_LENGTH = 32;
const RESTART_COOLDOWN_SECONDS = 10;
const LOGS_POLL_INTERVAL_MS = 3000;
// Telegram bot token format: numeric bot id, ":", then the 35-char API secret.
const BOT_TOKEN_PATTERN = /^\d+:[A-Za-z0-9_-]{35}$/;

function generateSecretToken(): string {
  return randomString(SECRET_TOKEN_CHARSET, SECRET_TOKEN_LENGTH);
}

function StatusBadge({ status }: { status: BotStatus }) {
  const { t } = useTranslation();
  // Configured: a token is stored. Running: Telegram has a webhook for it and
  // reports no delivery error, the only sign the bot actually answers.
  const queued =
    status.pending_update_count > 0
      ? t("settings.bot.pendingUpdates", { total: status.pending_update_count })
      : null;
  const failure =
    status.error !== null ? t("settings.bot.statusError", { message: status.error }) : null;
  const hint = [failure, queued].filter((line) => line !== null).join("\n\n") || null;
  const [tone, label] = !status.is_configured
    ? ["bg-warning/10 text-warning", t("settings.bot.notConfigured")]
    : status.is_running
      ? ["bg-success/10 text-success", t("settings.bot.running")]
      : ["bg-error/10 text-error", t("settings.bot.stopped")];

  return (
    <span
      className={`flex h-9 shrink-0 items-center gap-1.5 rounded-full border border-transparent px-4 text-[13px] font-semibold ${tone}`}
    >
      {label}
      {hint !== null && <FieldHint text={hint} side="bottom" align="end" />}
    </span>
  );
}

function BotLogsDialogBody() {
  const { t } = useTranslation();
  const [state, reload] = useAsyncResource(getBotLogs);

  // the next poll waits for the previous answer: a fixed interval aborted any
  // response slower than itself, so on a slow backend the logs never arrived
  useEffect(() => {
    if (state.kind === "loading") return;
    const timer = setTimeout(reload, LOGS_POLL_INTERVAL_MS);
    return () => clearTimeout(timer);
  }, [state, reload]);

  const logRef = useRef<HTMLPreElement>(null);
  // follows the tail unless the user scrolled up to read older lines
  const stickToBottomRef = useRef(true);

  useLayoutEffect(() => {
    const el = logRef.current;
    if (el && stickToBottomRef.current) el.scrollTop = el.scrollHeight;
  }, [state]);

  return (
    <>
      <DialogHeader
        icon={ScrollText}
        title={t("settings.bot.logsTitle")}
        actions={
          <>
            {state.kind === "loading" && <Spinner />}
            <motion.button
              type="button"
              onClick={reload}
              {...bounceTap()}
              className="flex h-8 w-fit items-center rounded-full border border-border px-3 text-xs font-medium text-foreground/80 transition-colors hover:bg-white/[0.06]"
            >
              {t("settings.bot.refreshLogs")}
            </motion.button>
          </>
        }
      />
      <div className="flex h-[70vh] flex-col p-5">
        <pre
          ref={logRef}
          onScroll={(event) => {
            const el = event.currentTarget;
            stickToBottomRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 16;
          }}
          className="min-h-0 flex-1 overflow-auto whitespace-pre-wrap break-all rounded-xl border border-border bg-input/60 p-3 font-mono text-[12px] leading-relaxed text-foreground/80">
          {state.kind === "error"
            ? t("settings.bot.logsLoadError")
            : state.kind === "ready"
              ? state.data.length > 0
                ? state.data.join("\n")
                : t("settings.bot.logsEmpty")
              : null}
        </pre>
      </div>
    </>
  );
}

export function BotSettingsForm() {
  const { t } = useTranslation();
  const permissions = usePermissions();
  const canManage = permissions.includes("BOT_SETTINGS_MANAGE");
  const canSetProxy = permissions.includes("BOT_PROXY_SET");
  const canViewStatus = permissions.includes("BOT_STATUS_VIEW");
  const [token, setToken] = useState("");
  const [secretToken, setSecretToken] = useState("");
  const [proxyUrl, setProxyUrl] = useState("");
  const [isRemovingProxy, setIsRemovingProxy] = useState(false);
  const [dropPendingUpdates, setDropPendingUpdates] = useState(false);
  const [initialDropPendingUpdates, setInitialDropPendingUpdates] = useState(false);
  const [state, , setData] = useAsyncResource(getBotSettings, {
    onSuccess: (settings) => {
      setDropPendingUpdates(settings.drop_pending_updates);
      setInitialDropPendingUpdates(settings.drop_pending_updates);
    },
  });
  // without the permission the status stays "loading" forever and its badge is hidden
  const [statusState, reloadStatus] = useAsyncResource((signal) =>
    canViewStatus ? getBotStatus(signal) : new Promise<BotStatus>(() => {}),
  );
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isRestarting, setIsRestarting] = useState(false);
  const [restartCooldown, setRestartCooldown] = useState(0);
  const [isSecretCopied, setIsSecretCopied] = useState(false);
  const [isLogsOpen, setIsLogsOpen] = useState(false);

  useEffect(() => {
    if (restartCooldown === 0) return;
    const timer = setTimeout(() => setRestartCooldown((seconds) => seconds - 1), 1000);
    return () => clearTimeout(timer);
  }, [restartCooldown]);

  const handleGenerateSecretToken = () => {
    const generated = generateSecretToken();
    setSecretToken(generated);
    void copyToClipboard(generated).then((copied) => {
      if (!copied) return;
      setIsSecretCopied(true);
      setTimeout(() => setIsSecretCopied(false), 1500);
    });
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const hasSettingsChanges =
      Boolean(token || secretToken) || dropPendingUpdates !== initialDropPendingUpdates;
    const proxy = proxyUrl.trim();

    if (!hasSettingsChanges && !proxy) {
      toast.error(t("settings.bot.errorEmptyFields"));
      return;
    }

    if (token && !BOT_TOKEN_PATTERN.test(token)) {
      toast.error(t("settings.bot.errorInvalidToken"));
      return;
    }

    setIsSubmitting(true);

    try {
      let settings: BotSettings | null = null;
      if (hasSettingsChanges) {
        settings = await updateBotSettings({
          token: token || undefined,
          secret_token: secretToken || undefined,
          drop_pending_updates: dropPendingUpdates,
        });
        setToken("");
        setSecretToken("");
        setInitialDropPendingUpdates(settings.drop_pending_updates);
      }
      if (proxy) {
        settings = await setBotProxy(proxy);
        setProxyUrl("");
      }
      if (settings !== null) setData(settings);
      reloadStatus();
      toast.success(t("common.saved"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRemoveProxy = async () => {
    setIsRemovingProxy(true);

    try {
      setData(await removeBotProxy());
      setProxyUrl("");
      toast.success(t("settings.bot.proxyRemoved"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    } finally {
      setIsRemovingProxy(false);
    }
  };

  const isProxyConfigured = state.kind === "ready" && state.data.is_proxy_configured;

  const handleRestart = async () => {
    setIsRestarting(true);
    setRestartCooldown(RESTART_COOLDOWN_SECONDS);

    try {
      await restartBot();
      reloadStatus();
      toast.success(t("settings.bot.restartRequested"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    } finally {
      setIsRestarting(false);
    }
  };

  return (
    <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-4">
        <CardHeader
          icon={Bot}
          title={t("settings.bot.title")}
          description={t("settings.bot.description")}
          aside={
            <>
              {permissions.includes("BOT_LOGS_VIEW") && (
                <Button variant="outline" onClick={() => setIsLogsOpen(true)}>
                  {t("settings.bot.showLogs")}
                </Button>
              )}
              {state.kind === "loading" && <Spinner />}
              {statusState.kind === "ready" && <StatusBadge status={statusState.data} />}
              {(state.kind === "error" || statusState.kind === "error") && (
                <span className="flex h-9 shrink-0 items-center rounded-full border border-transparent bg-error/10 px-4 text-[13px] font-semibold text-error">
                  {t("settings.bot.loadErrorBadge")}
                </span>
              )}
            </>
          }
        />

        <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-3">
          <fieldset disabled={!canManage} className="contents">
          <div className="flex flex-col gap-1">
            <label
              htmlFor="bot-token"
              className="flex items-center gap-1.5 text-sm font-medium text-foreground/80"
            >
              {t("settings.bot.tokenLabel")}
              <FieldHint text={t("settings.bot.tokenHint")} />
            </label>
            <input
              id="bot-token"
              type="password"
              value={token}
              onChange={(event) => setToken(event.target.value)}
              placeholder={t("settings.bot.placeholder")}
              autoComplete="off"
              className="min-w-0 rounded-full border border-border bg-input/60 h-9 px-3 text-sm text-foreground outline-none focus:border-primary disabled:cursor-not-allowed disabled:opacity-50"
            />
          </div>

          <div className="flex flex-col gap-1">
            <label
              htmlFor="bot-secret-token"
              className="flex items-center gap-1.5 text-sm font-medium text-foreground/80"
            >
              {t("settings.bot.secretTokenLabel")}
              <FieldHint text={t("settings.bot.secretTokenHint")} />
            </label>
            <div className="relative">
              <input
                id="bot-secret-token"
                type="password"
                value={secretToken}
                onChange={(event) => setSecretToken(event.target.value)}
                placeholder={t("settings.bot.placeholder")}
                autoComplete="off"
                className="min-w-0 w-full rounded-full border border-border bg-input/60 px-3 py-2 pr-24 text-sm text-foreground outline-none focus:border-primary disabled:cursor-not-allowed disabled:opacity-50"
              />
              <motion.button
                type="button"
                onClick={handleGenerateSecretToken}
                {...bounceTap()}
                className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded-full px-2.5 py-1 text-xs font-medium text-muted-foreground transition-colors hover:bg-white/[0.07] hover:text-foreground"
              >
                {isSecretCopied ? t("settings.bot.secretTokenCopied") : t("settings.bot.generateSecretToken")}
              </motion.button>
            </div>
          </div>

          </fieldset>

          <div className="flex flex-col gap-1">
            <label
              htmlFor="bot-proxy-url"
              className="flex items-center gap-1.5 text-sm font-medium text-foreground/80"
            >
              {t("settings.bot.proxyLabel")}
              <FieldHint text={t("settings.bot.proxyHint")} />
            </label>
            <div className="relative">
              <input
                id="bot-proxy-url"
                type="password"
                value={proxyUrl}
                onChange={(event) => setProxyUrl(event.target.value)}
                placeholder={
                  isProxyConfigured
                    ? t("settings.bot.proxyConfiguredPlaceholder")
                    : t("settings.bot.proxyPlaceholder")
                }
                autoComplete="off"
                disabled={!canSetProxy}
                className={`min-w-0 w-full rounded-full border border-border bg-input/60 px-3 py-2 text-sm text-foreground outline-none focus:border-primary disabled:cursor-not-allowed disabled:opacity-50 ${isProxyConfigured ? "pr-24" : ""}`}
              />
              {isProxyConfigured && permissions.includes("BOT_PROXY_REMOVE") && (
                <motion.button
                  type="button"
                  onClick={() => void handleRemoveProxy()}
                  disabled={isRemovingProxy}
                  {...bounceTap()}
                  className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded-full px-2.5 py-1 text-xs font-medium text-muted-foreground transition-colors hover:bg-white/[0.07] hover:text-foreground"
                >
                  {t("settings.bot.removeProxy")}
                </motion.button>
              )}
            </div>
          </div>

          <fieldset disabled={!canManage} className="flex items-center justify-between gap-3 py-2">
            <span className="flex items-center gap-1.5 text-sm text-foreground/80">
              {t("settings.bot.dropPendingUpdatesLabel")}
              <FieldHint text={t("settings.bot.dropPendingUpdatesHint")} />
            </span>
            <Switch
              checked={dropPendingUpdates}
              onChange={setDropPendingUpdates}
            />
          </fieldset>


          <div className="flex items-center gap-2">
            {(canManage || canSetProxy) && (
              <Button
                variant="accent"
                className="w-fit"
                type="submit"
                disabled={isSubmitting}
              >
                {isSubmitting ? t("common.saving") : t("common.save")}
              </Button>
            )}

            {permissions.includes("BOT_RESTART") && (
            <Button
              variant="outline"
              className="w-fit"
              type="button"
              onClick={() => void handleRestart()}
              disabled={isRestarting || restartCooldown > 0}
            >
              {isRestarting
                ? t("settings.bot.restarting")
                : restartCooldown > 0
                  ? t("settings.bot.restartCooldown", { seconds: restartCooldown })
                  : t("settings.bot.restartBot")}
            </Button>
            )}

            <FieldHint text={t("settings.bot.applyChangesDescription")} />
          </div>
        </form>

        {isLogsOpen && (
          <Modal onClose={() => setIsLogsOpen(false)} size="xl" scrollable>
            <BotLogsDialogBody />
          </Modal>
        )}
    </div>
  );
}
