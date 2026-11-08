import { Bot, Check, Copy, RefreshCw, ScrollText, Trash2 } from "lucide-react";
import { useEffect, useLayoutEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { ApiError, getErrorMessage } from "@shared/api/http";
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
import { randomString } from "@shared/lib/random-string";
import { toast } from "@shared/lib/toast";
import { useFieldValidation } from "@shared/lib/use-field-validation";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { FieldHint } from "@shared/ui/FieldHint";
import { StatusPill } from "@shared/ui/glass/StatusPill";
import { Modal } from "@shared/ui/Modal";
import { Spinner } from "@shared/ui/Spinner";
import { Button } from "@shared/ui/Button";
import { DialogHeader } from "@shared/ui/glass/DialogHeader";
import { Field } from "@shared/ui/glass/Field";
import { Input, PasswordInput } from "@shared/ui/glass/Input";
import { Row } from "@shared/ui/glass/Row";
import { Section, SectionFields, SectionRows } from "@shared/ui/glass/Section";
import { Switch } from "@shared/ui/glass/Switch";
import { IconButton } from "@shared/ui/IconButton";
import { Pressable } from "@shared/ui/Pressable";
import { SaveFooter } from "@shared/ui/SaveFooter";

// Telegram's secret_token requirement: 1-256 chars, only A-Z, a-z, 0-9, "_", "-".
const SECRET_TOKEN_CHARSET =
  "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-";
const SECRET_TOKEN_LENGTH = 32;
const RESTART_COOLDOWN_SECONDS = 10;
const LOGS_POLL_INTERVAL_MS = 3000;
// Telegram bot token format: numeric bot id, ":", then the 35-char API secret.
const BOT_TOKEN_PATTERN = /^\d+:[A-Za-z0-9_-]{35}$/;
// what Telegram's setWebhook takes as a secret_token
const SECRET_TOKEN_PATTERN = /^[A-Za-z0-9_-]{1,256}$/;
// the backend's check (set_bot_proxy.py): scheme://[user:password@]host:port with one of its schemes.
// A pattern, not new URL(): browsers long parsed no host out of non-web schemes like socks5://
const PROXY_URL_PATTERN = /^(?:http|socks5h?):\/\/(?:[^@/\s]+@)?(?:\[[0-9a-f:.]+\]|[^:/\s@]+):\d{1,5}\/?$/i;

function isProxyUrl(value: string): boolean {
  return PROXY_URL_PATTERN.test(value);
}

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
    ? (["warning", t("settings.bot.notConfigured")] as const)
    : status.is_running
      ? (["success", t("settings.bot.running")] as const)
      : (["error", t("settings.bot.stopped")] as const);

  return (
    <StatusPill tone={tone}>
      {label}
      {hint !== null && <FieldHint text={hint} side="bottom" align="end" />}
    </StatusPill>
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
  const [isCopied, setIsCopied] = useState(false);
  // the last lines that arrived: a poll in flight shouldn't grey the button out
  const linesRef = useRef<string[]>([]);
  if (state.kind === "ready") linesRef.current = state.data;
  const hasLines = linesRef.current.length > 0;
  const copyLogs = async () => {
    if (!(await copyToClipboard(linesRef.current.join("\n")))) return;
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 1500);
  };
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
            <Button variant="glass" disabled={!hasLines} onClick={() => void copyLogs()}>
              {isCopied ? <Check className="size-4 text-primary" /> : <Copy className="size-4" />}
              {t(isCopied ? "settings.bot.logsCopied" : "settings.bot.copyLogs")}
            </Button>
            {/* spins while a poll or a manual refresh is in flight */}
            <IconButton size="9" tone="glass" onClick={reload}>
              {/* Copy's icon size and colour, not IconButton's muted one: the two read as a pair */}
              <RefreshCw className={`size-4 text-foreground/90 ${state.kind === "loading" ? "animate-spin" : ""}`} />
            </IconButton>
          </>
        }
      />
      <div className="flex h-[70vh] flex-col p-3">
        {/* the well and its corners on a clipping wrapper: a scrollbar ignores its own element's
            rounded corners, not an ancestor's clip */}
        <div className="glass-well flex min-h-0 flex-1 overflow-hidden rounded-xl">
          <pre
            ref={logRef}
            onScroll={(event) => {
              const el = event.currentTarget;
              stickToBottomRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 16;
            }}
            className="min-h-0 flex-1 overflow-auto whitespace-pre-wrap break-all p-3.5 font-mono text-[12px] leading-relaxed text-foreground/80"
          >
            {state.kind === "error"
              ? t("settings.bot.logsLoadError")
              : state.kind === "ready"
                ? state.data.length > 0
                  ? state.data.join("\n")
                  : t("settings.bot.logsEmpty")
                : null}
          </pre>
        </div>
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

  const validation = useFieldValidation<"token" | "secretToken" | "proxy">();
  const errors = {
    token: token && !BOT_TOKEN_PATTERN.test(token) ? t("settings.bot.errorInvalidToken") : null,
    secretToken: secretToken && !SECRET_TOKEN_PATTERN.test(secretToken) ? t("settings.bot.secretTokenInvalid") : null,
    proxy: proxyUrl.trim() && !isProxyUrl(proxyUrl.trim()) ? t("apiErrors.BOT_PROXY_URL_INVALID") : null,
  };
  const shown = (name: keyof typeof errors) => validation.visible(name, errors[name]);
  const watch = (name: keyof typeof errors) => ({
    onBlur: validation.touch(name),
    "aria-invalid": shown(name) !== undefined,
  });

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const hasSettingsChanges =
      Boolean(token || secretToken) || dropPendingUpdates !== initialDropPendingUpdates;
    const proxy = proxyUrl.trim();
    validation.submit();
    if ((!hasSettingsChanges && !proxy) || Object.values(errors).some((error) => error !== null)) return;

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
      validation.reset();
      toast.success(t("common.saved"));
    } catch (err) {
      // the backend's own proxy check: said under the field
      if (err instanceof ApiError && err.code === "BOT_PROXY_URL_INVALID") {
        validation.setServerError("proxy", getErrorMessage(err, t("common.errors.generic")));
      } else {
        toast.error(getErrorMessage(err, t("common.errors.generic")));
      }
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

  const dirty =
    Boolean(token || secretToken || proxyUrl.trim()) || dropPendingUpdates !== initialDropPendingUpdates;
  const canSave = canManage || canSetProxy;
  // without a token the process restarts into the same idle app: nothing to apply yet
  const isConfigured = state.kind === "ready" && state.data.is_configured;
  const restartButton = permissions.includes("BOT_RESTART") && (
    // a spinner through the request and the cooldown after it, not a countdown
    <Button
      variant="glass"
      onClick={() => void handleRestart()}
      disabled={!isConfigured}
      isLoading={isRestarting || restartCooldown > 0}
    >
      {t("settings.bot.restartBot")}
    </Button>
  );
  const beside = (
    <>
      {restartButton}
      <FieldHint text={t("settings.bot.applyChangesDescription")} />
    </>
  );

  return (
    <form onSubmit={(event) => void handleSubmit(event)}>
      <Section
        icon={Bot}
        title={t("settings.bot.title")}
        description={t("settings.bot.description")}
        aside={
          <>
            {permissions.includes("BOT_LOGS_VIEW") && (
              <Button variant="glass" icon={ScrollText} onClick={() => setIsLogsOpen(true)}>
                {t("settings.bot.showLogs")}
              </Button>
            )}
            {state.kind === "loading" && <Spinner />}
            {statusState.kind === "ready" && <StatusBadge status={statusState.data} />}
            {(state.kind === "error" || statusState.kind === "error") && (
              <StatusPill tone="error">{t("settings.bot.loadErrorBadge")}</StatusPill>
            )}
          </>
        }
        footer={
          canSave ? (
            <SaveFooter variant="glassAccent" dirty={dirty} saving={isSubmitting} beside={beside} />
          ) : (
            restartButton && <div className="mt-4 flex items-center gap-3">{beside}</div>
          )
        }
      >
        <SectionFields>
          <fieldset disabled={!canManage} className="contents">
            <Field label={t("settings.bot.tokenLabel")} htmlFor="bot-token" info={t("settings.bot.tokenHint")} error={shown("token")}>
              <PasswordInput
                id="bot-token"
                value={token}
                onChange={(event) => setToken(event.target.value)}
                {...watch("token")}
                placeholder={t("settings.bot.placeholder")}
                autoComplete="off"
              />
            </Field>
            <Field
              label={t("settings.bot.secretTokenLabel")}
              htmlFor="bot-secret-token"
              info={t("settings.bot.secretTokenHint")}
              error={shown("secretToken")}
            >
              <Input
                id="bot-secret-token"
                type="password"
                value={secretToken}
                onChange={(event) => setSecretToken(event.target.value)}
                {...watch("secretToken")}
                placeholder={t("settings.bot.placeholder")}
                autoComplete="off"
                end={
                  <InlineAction onClick={handleGenerateSecretToken}>
                    {isSecretCopied ? t("settings.bot.secretTokenCopied") : t("settings.bot.generateSecretToken")}
                  </InlineAction>
                }
              />
            </Field>
          </fieldset>
          <Field label={t("settings.bot.proxyLabel")} htmlFor="bot-proxy-url" info={t("settings.bot.proxyHint")} error={shown("proxy")}>
            <Input
              id="bot-proxy-url"
              type="password"
              value={proxyUrl}
              onChange={(event) => {
                setProxyUrl(event.target.value);
                validation.changed("proxy");
              }}
              {...watch("proxy")}
              placeholder={
                isProxyConfigured ? t("settings.bot.proxyConfiguredPlaceholder") : t("settings.bot.proxyPlaceholder")
              }
              autoComplete="off"
              disabled={!canSetProxy}
              end={
                isProxyConfigured &&
                permissions.includes("BOT_PROXY_REMOVE") && (
                  <InlineAction onClick={() => void handleRemoveProxy()} disabled={isRemovingProxy}>
                    {t("settings.bot.removeProxy")}
                  </InlineAction>
                )
              }
            />
          </Field>
        </SectionFields>
        <fieldset disabled={!canManage} className="contents">
          <SectionRows divided>
            <Row icon={Trash2} label={t("settings.bot.dropPendingUpdatesLabel")} hint={t("settings.bot.dropPendingUpdatesHint")}>
              <Switch checked={dropPendingUpdates} onChange={setDropPendingUpdates} />
            </Row>
          </SectionRows>
        </fieldset>

        {isLogsOpen && (
          <Modal onClose={() => setIsLogsOpen(false)} size="xl" scrollable>
            <BotLogsDialogBody />
          </Modal>
        )}
      </Section>
    </form>
  );
}

// a 28px text action inside a field's well, 4px in (on the 36px well's curve)
function InlineAction({ onClick, disabled = false, children }: { onClick: () => void; disabled?: boolean; children: ReactNode }) {
  return (
    <Pressable
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="flex h-7 shrink-0 items-center rounded-full px-3 text-[12px] font-medium text-muted-foreground transition-colors hover:bg-white/[0.06] hover:text-foreground disabled:opacity-50"
    >
      {children}
    </Pressable>
  );
}
