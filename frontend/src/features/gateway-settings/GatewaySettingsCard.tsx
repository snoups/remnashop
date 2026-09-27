import { BookOpen, Check, ChevronDown, Copy } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import {
  createTestPayment,
  getTestPaymentStatus,
  toggleGatewayActive,
  updateGatewaySettings,
  type Gateway,
  type GatewayFieldSpec,
  type TestPaymentStatus,
} from "@entities/gateways/api";
import { getErrorMessage } from "@shared/api/http";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { toast } from "@shared/lib/toast";
import { Switch } from "@shared/ui/Switch";

import { GATEWAY_DOCS_URLS } from "./docs-links";
import { inputModeFor, sanitizeFieldValue } from "./field-input";

const TEST_PAYMENT_POLL_MS = 3000;

interface GatewaySettingsCardProps {
  gateway: Gateway;
  fields: GatewayFieldSpec[];
  webhookUrl: string | null;
  onChanged: (gateway: Gateway) => void;
}

function inputTypeFor(kind: GatewayFieldSpec["kind"]): string {
  return kind === "secret" ? "password" : "text";
}

export function GatewaySettingsCard({
  gateway,
  fields,
  webhookUrl,
  onChanged,
}: GatewaySettingsCardProps) {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const [isOpen, setIsOpen] = useState(false);
  const [values, setValues] = useState<Record<string, string>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isToggling, setIsToggling] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [testOrderId, setTestOrderId] = useState<number | null>(null);
  const [testStatus, setTestStatus] = useState<TestPaymentStatus | null>(null);
  const [isWebhookCopied, setIsWebhookCopied] = useState(false);

  const label = t(`settings.gateways.types.${gateway.type}`);
  const docsUrl = GATEWAY_DOCS_URLS[gateway.type];
  const canExpand = fields.length > 0 || webhookUrl !== null;
  // Stars pays inside the bot, there is no provider page to open
  const canTest = gateway.is_configured && gateway.type !== "TELEGRAM_STARS";

  const toggleOpen = () => {
    if (canExpand) setIsOpen((open) => !open);
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const changed = Object.fromEntries(Object.entries(values).filter(([, value]) => value !== ""));
    if (Object.keys(changed).length === 0) {
      toast.error(t("settings.gateways.errorEmptyFields"));
      return;
    }

    setIsSubmitting(true);
    try {
      onChanged(await updateGatewaySettings(gateway.type, changed));
      setValues({});
      toast.success(t("settings.gateways.saved"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("auth.errors.genericError")));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCopyWebhook = () => {
    if (webhookUrl === null) return;
    navigator.clipboard?.writeText(webhookUrl).catch(() => {});
    setIsWebhookCopied(true);
    setTimeout(() => setIsWebhookCopied(false), 1500);
  };

  const handleToggle = async () => {
    setIsToggling(true);
    try {
      onChanged(await toggleGatewayActive(gateway.type));
    } catch (err) {
      toast.error(getErrorMessage(err, t("settings.gateways.toggleError")));
    } finally {
      setIsToggling(false);
    }
  };

  useEffect(() => {
    if (testOrderId === null || testStatus !== "PENDING") return;
    const timer = setInterval(() => {
      getTestPaymentStatus(testOrderId)
        .then(({ status }) => {
          if (status === "PENDING") return;
          setTestStatus(status);
          if (status === "PAID") toast.success(t("settings.gateways.testPaymentPaid"));
        })
        .catch(() => {});
    }, TEST_PAYMENT_POLL_MS);
    return () => clearInterval(timer);
  }, [testOrderId, testStatus, t]);

  const handleTestPayment = async () => {
    // opened synchronously so the popup blocker treats it as user-initiated
    const tab = window.open("", "_blank");
    setIsTesting(true);
    try {
      const { order_id, confirmation_url } = await createTestPayment(gateway.type);
      setTestOrderId(order_id);
      setTestStatus("PENDING");
      if (tab && confirmation_url) {
        tab.opener = null;
        tab.location.href = confirmation_url;
      } else {
        tab?.close();
      }
    } catch (err) {
      tab?.close();
      toast.error(getErrorMessage(err, t("settings.gateways.testPaymentError")));
    } finally {
      setIsTesting(false);
    }
  };

  return (
    <div>
      <motion.div
        role="button"
        tabIndex={0}
        onClick={toggleOpen}
        onKeyDown={(event) => {
          if (event.key !== "Enter" && event.key !== " ") return;
          event.preventDefault();
          toggleOpen();
        }}
        {...bounceTap(bounceStrength, 0.03)}
        className={`flex items-center gap-3 rounded-full px-[12.5px] py-2.5 transition-colors hover:bg-white/[0.04] ${canExpand ? "cursor-pointer" : ""}`}
      >
        <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-white/[0.06] text-[13px] font-bold text-foreground">
          {label.charAt(0)}
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-[13px] font-medium text-foreground">{label}</p>
          <p className="text-[12px]">
            {gateway.is_configured ? (
              <span className="text-success">{t("settings.gateways.configured")}</span>
            ) : (
              <span className="text-warning">{t("settings.gateways.notConfigured")}</span>
            )}
          </p>
        </div>
        {canExpand && (
          <span className="flex size-6 shrink-0 items-center justify-center">
            <ChevronDown
              className={`size-4 text-muted-foreground transition-transform ${isOpen ? "rotate-180" : ""}`}
            />
          </span>
        )}
        {docsUrl && (
          <a
            href={docsUrl}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(event) => event.stopPropagation()}
            aria-label={t("settings.gateways.docsAria", { gateway: label })}
            className="flex size-6 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-white/[0.08] hover:text-foreground"
          >
            <BookOpen className="size-4" />
          </a>
        )}
        <div className="flex" onClick={(event) => event.stopPropagation()}>
          <Switch
            checked={gateway.is_active}
            onChange={() => void handleToggle()}
            disabled={isToggling || !gateway.is_configured}
            ariaLabel={t("settings.gateways.enableAria", { gateway: label })}
          />
        </div>
      </motion.div>

      <AnimatePresence initial={false}>
        {isOpen && canExpand && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            className="overflow-hidden"
          >
            <form
              onSubmit={(event) => void handleSubmit(event)}
              className="flex flex-col gap-3 px-[12.5px] pb-2 pt-1"
            >
              {webhookUrl !== null && (
                <div className="flex flex-col gap-1">
                  <span className="text-sm font-medium text-foreground/80">
                    {t("settings.gateways.webhookLabel")}
                  </span>
                  <div className="flex items-center justify-between gap-2 rounded-xl border border-border bg-input/60 px-3 py-2">
                    <span className="truncate font-mono text-[13px] text-foreground">{webhookUrl}</span>
                    <button
                      type="button"
                      onClick={handleCopyWebhook}
                      aria-label={t("settings.gateways.copyWebhookAria")}
                      className="flex size-7 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-white/[0.08] hover:text-foreground"
                    >
                      {isWebhookCopied ? <Check className="size-3.5 text-success" /> : <Copy className="size-3.5" />}
                    </button>
                  </div>
                </div>
              )}
              {fields.map((field) => (
                <div key={field.key} className="flex flex-col gap-1">
                  <label className="text-sm font-medium text-foreground/80">
                    {t(`settings.gateways.fields.${gateway.type}.${field.key}`)}
                  </label>
                  <input
                    type={inputTypeFor(field.kind)}
                    inputMode={inputModeFor(field)}
                    value={values[field.key] ?? ""}
                    onChange={(event) =>
                      setValues((prev) => ({
                        ...prev,
                        [field.key]: sanitizeFieldValue(field, event.target.value),
                      }))
                    }
                    placeholder={t("settings.gateways.placeholder")}
                    autoComplete="off"
                    className="rounded-xl border border-border bg-input/60 px-3 py-2 text-sm text-foreground outline-none focus:border-primary"
                  />
                </div>
              ))}
              {(fields.length > 0 || canTest) && (
                <div className="flex flex-wrap gap-2">
                  {fields.length > 0 && (
                    <motion.button
                      type="submit"
                      disabled={isSubmitting}
                      {...bounceTap(bounceStrength)}
                      className="w-fit rounded-full bg-accent px-4 py-2 text-sm font-medium text-primary transition-colors hover:bg-primary/20 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {isSubmitting ? t("settings.gateways.saving") : t("settings.gateways.save")}
                    </motion.button>
                  )}
                  {canTest && (
                    <motion.button
                      type="button"
                      onClick={() => void handleTestPayment()}
                      disabled={isTesting}
                      {...bounceTap(bounceStrength)}
                      className="w-fit rounded-full bg-white/[0.06] px-4 py-2 text-sm font-medium text-foreground transition-colors hover:bg-white/[0.1] disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {isTesting
                        ? t("settings.gateways.testPaymentCreating")
                        : t("settings.gateways.testPayment")}
                    </motion.button>
                  )}
                </div>
              )}
              {testStatus !== null && (
                <p
                  className={`text-[12px] ${
                    testStatus === "PAID"
                      ? "text-success"
                      : testStatus === "PENDING"
                        ? "text-muted-foreground"
                        : "text-warning"
                  }`}
                >
                  {t(`settings.gateways.testPaymentStatus.${testStatus}`)}
                </p>
              )}
            </form>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
