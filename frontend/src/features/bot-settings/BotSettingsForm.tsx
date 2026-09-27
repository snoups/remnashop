import { Bot, ScrollText, X } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { getErrorMessage } from "@shared/api/http";
import {
  getBotLogs,
  getBotSettings,
  getBotStatus,
  restartBot,
  updateBotSettings,
  type BotStatus,
} from "@entities/settings/api";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { randomString } from "@shared/lib/random-string";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { FieldHint } from "@shared/ui/FieldHint";
import { Modal, useModalClose } from "@shared/ui/Modal";
import { Spinner } from "@shared/ui/Spinner";
import { Switch } from "@shared/ui/Switch";

// Telegram's secret_token requirement: 1-256 chars, only A-Z, a-z, 0-9, "_", "-".
const SECRET_TOKEN_CHARSET =
  "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-";
const SECRET_TOKEN_LENGTH = 32;
const RESTART_COOLDOWN_SECONDS = 10;
// Telegram bot token format: numeric bot id, ":", then the 35-char API secret.
const BOT_TOKEN_PATTERN = /^\d+:[A-Za-z0-9_-]{35}$/;

function generateSecretToken(): string {
  return randomString(SECRET_TOKEN_CHARSET, SECRET_TOKEN_LENGTH);
}

function StatusBadge({ status }: { status: BotStatus }) {
  const { t } = useTranslation();
  // Configured means a token is stored; running means Telegram has a webhook
  // for it and isn't reporting a delivery error -- only the second one says
  // the bot is actually answering.
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
      className={`ml-auto flex shrink-0 items-center gap-1.5 rounded-full border border-transparent px-4 py-1.5 text-[13px] font-semibold ${tone}`}
    >
      {label}
      {hint !== null && <FieldHint text={hint} side="bottom" align="end" />}
    </span>
  );
}

function BotLogsDialogBody() {
  const { t } = useTranslation();
  const close = useModalClose();
  const bounceStrength = useBounceStrength();
  const [state, reload] = useAsyncResource(getBotLogs);

  return (
    <>
      <div className="flex shrink-0 items-center gap-2 border-b border-border px-5 py-4">
        <h2 className="flex items-center gap-2.5 text-base font-bold text-foreground">
          <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] backdrop-blur-md">
            <ScrollText className="size-4" />
          </div>
          {t("settings.bot.logsTitle")}
        </h2>
        {state.kind === "loading" && <Spinner />}
        <motion.button
          type="button"
          onClick={reload}
          {...bounceTap(bounceStrength)}
          className="ml-auto flex h-8 w-fit items-center rounded-full border border-border px-3 text-xs font-medium text-foreground/80 transition-colors hover:bg-white/5"
        >
          {t("settings.bot.refreshLogs")}
        </motion.button>
        <button
          type="button"
          onClick={close}
          aria-label={t("settings.bot.closeLogs")}
          className="flex size-8 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-white/[0.06] hover:text-foreground"
        >
          <X className="size-4" />
        </button>
      </div>
      <div className="flex min-h-0 flex-1 flex-col p-5">
        <pre className="min-h-0 flex-1 overflow-auto whitespace-pre-wrap break-all rounded-xl border border-border bg-input/60 p-3 font-mono text-[11.5px] leading-relaxed text-foreground/80">
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
  const bounceStrength = useBounceStrength();
  const [token, setToken] = useState("");
  const [secretToken, setSecretToken] = useState("");
  const [dropPendingUpdates, setDropPendingUpdates] = useState(false);
  const [initialDropPendingUpdates, setInitialDropPendingUpdates] = useState(false);
  const [state, , setData] = useAsyncResource(getBotSettings, (settings) => {
    setDropPendingUpdates(settings.drop_pending_updates);
    setInitialDropPendingUpdates(settings.drop_pending_updates);
  });
  const [statusState, reloadStatus] = useAsyncResource(getBotStatus);
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
    navigator.clipboard?.writeText(generated).catch(() => {});
    setIsSecretCopied(true);
    setTimeout(() => setIsSecretCopied(false), 1500);
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (!token && !secretToken && dropPendingUpdates === initialDropPendingUpdates) {
      toast.error(t("settings.bot.errorEmptyFields"));
      return;
    }

    if (token && !BOT_TOKEN_PATTERN.test(token)) {
      toast.error(t("settings.bot.errorInvalidToken"));
      return;
    }

    setIsSubmitting(true);

    try {
      const settings = await updateBotSettings({
        token: token || undefined,
        secret_token: secretToken || undefined,
        drop_pending_updates: dropPendingUpdates,
      });
      setData(settings);
      setToken("");
      setSecretToken("");
      setInitialDropPendingUpdates(settings.drop_pending_updates);
      reloadStatus();
      toast.success(t("settings.bot.saved"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("auth.errors.genericError")));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRestart = async () => {
    setIsRestarting(true);
    setRestartCooldown(RESTART_COOLDOWN_SECONDS);

    try {
      await restartBot();
      reloadStatus();
      toast.success(t("settings.bot.restartRequested"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("auth.errors.genericError")));
    } finally {
      setIsRestarting(false);
    }
  };

  return (
    <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-4">
        <div className="flex items-center gap-2.5">
          <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] text-foreground backdrop-blur-md">
            <Bot className="size-4" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-foreground">{t("settings.bot.title")}</h2>
            <p className="mt-0.5 text-[12.5px] text-muted-foreground">{t("settings.bot.description")}</p>
          </div>
          {state.kind === "loading" && <Spinner className="ml-auto" />}
          {statusState.kind === "ready" && <StatusBadge status={statusState.data} />}
          {(state.kind === "error" || statusState.kind === "error") && (
            <span className="ml-auto shrink-0 rounded-full border border-transparent bg-error/10 px-4 py-1.5 text-[13px] font-semibold text-error">
              {t("settings.bot.loadErrorBadge")}
            </span>
          )}
        </div>

        <div className="-mx-4 mt-4 border-t border-white/[0.07]" />

        <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-3">
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
              className="min-w-0 rounded-xl border border-border bg-input/60 px-3 py-2 text-sm text-foreground outline-none focus:border-primary"
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
                className="min-w-0 w-full rounded-xl border border-border bg-input/60 px-3 py-2 pr-24 text-sm text-foreground outline-none focus:border-primary"
              />
              <motion.button
                type="button"
                onClick={handleGenerateSecretToken}
                {...bounceTap(bounceStrength)}
                className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded-full px-2.5 py-1 text-xs font-medium text-muted-foreground transition-colors hover:bg-white/[0.1] hover:text-foreground"
              >
                {isSecretCopied ? t("settings.bot.secretTokenCopied") : t("settings.bot.generateSecretToken")}
              </motion.button>
            </div>
          </div>

          <div className="flex items-center justify-between gap-3 py-2">
            <span className="flex items-center gap-1.5 text-sm text-foreground/80">
              {t("settings.bot.dropPendingUpdatesLabel")}
              <FieldHint text={t("settings.bot.dropPendingUpdatesHint")} />
            </span>
            <Switch
              checked={dropPendingUpdates}
              onChange={setDropPendingUpdates}
              ariaLabel={t("settings.bot.dropPendingUpdatesLabel")}
            />
          </div>


          <div className="flex items-center gap-2">
            <motion.button
              type="submit"
              disabled={isSubmitting}
              {...bounceTap(bounceStrength)}
              className="w-fit rounded-full bg-accent px-4 py-2 text-sm font-medium text-primary transition-colors hover:bg-primary/20 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isSubmitting ? t("settings.bot.saving") : t("settings.bot.save")}
            </motion.button>

            <motion.button
              type="button"
              onClick={() => void handleRestart()}
              disabled={isRestarting || restartCooldown > 0}
              {...bounceTap(bounceStrength)}
              className="w-fit rounded-full border border-border px-4 py-2 text-sm font-medium text-foreground/80 transition-colors hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isRestarting
                ? t("settings.bot.restarting")
                : restartCooldown > 0
                  ? t("settings.bot.restartCooldown", { seconds: restartCooldown })
                  : t("settings.bot.restartBot")}
            </motion.button>

            <FieldHint text={t("settings.bot.applyChangesDescription")} />

            <motion.button
              type="button"
              onClick={() => setIsLogsOpen(true)}
              {...bounceTap(bounceStrength)}
              className="ml-auto w-fit rounded-full border border-border px-4 py-2 text-sm font-medium text-foreground/80 transition-colors hover:bg-white/5"
            >
              {t("settings.bot.showLogs")}
            </motion.button>
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
