import { BookOpen, ChevronDown } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import {
  createTestPayment,
  getTestPaymentStatus,
  setGatewayActive,
  updateGatewaySettings,
  type Gateway,
  type GatewayFieldSpec,
  type TestPaymentStatus,
} from "@entities/gateways/api";
import { getErrorMessage } from "@shared/api/http";
import { bounceTap } from "@shared/lib/bounceState";
import { isHttpsUrl } from "@shared/lib/external-links";
import { toast } from "@shared/lib/toast";
import { Switch } from "@shared/ui/Switch";
import { Button } from "@shared/ui/Button";
import { TextInput } from "@shared/ui/TextInput";
import { Field } from "@shared/ui/Field";
import { CopyableValue } from "@shared/ui/CopyableValue";

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
  const [isOpen, setIsOpen] = useState(false);
  const [values, setValues] = useState<Record<string, string>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isToggling, setIsToggling] = useState(false);
  const [savingFlag, setSavingFlag] = useState<string | null>(null);
  const [isTesting, setIsTesting] = useState(false);
  const [testOrderId, setTestOrderId] = useState<number | null>(null);
  const [testStatus, setTestStatus] = useState<TestPaymentStatus | null>(null);

  const label = t(`settings.gateways.types.${gateway.type}`);
  const flagFields = fields.filter((field) => field.kind === "boolean");
  const valueFields = fields.filter((field) => field.kind !== "boolean");
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

  const handleFlag = async (key: string, enabled: boolean) => {
    setSavingFlag(key);
    try {
      onChanged(await updateGatewaySettings(gateway.type, { [key]: String(enabled) }));
    } catch (err) {
      toast.error(getErrorMessage(err, t("auth.errors.genericError")));
    } finally {
      setSavingFlag(null);
    }
  };

  const handleToggle = async () => {
    setIsToggling(true);
    try {
      onChanged(await setGatewayActive(gateway.type, !gateway.is_active));
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
      if (tab && confirmation_url && isHttpsUrl(confirmation_url)) {
        tab.opener = null;
        tab.location.href = confirmation_url;
      } else {
        tab?.close();
        if (confirmation_url) toast.error(t("settings.gateways.testPaymentBadUrl"));
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
        tabIndex={0}
        onClick={toggleOpen}
        onKeyDown={(event) => {
          if (event.key !== "Enter" && event.key !== " ") return;
          event.preventDefault();
          toggleOpen();
        }}
        {...bounceTap(0.03)}
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
            className="flex size-6 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-white/[0.06] hover:text-foreground"
          >
            <BookOpen className="size-4" />
          </a>
        )}
        <div className="mr-1 flex" onClick={(event) => event.stopPropagation()}>
          <Switch
            checked={gateway.is_active}
            onChange={() => void handleToggle()}
            disabled={isToggling || !gateway.is_configured}
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
                <Field label={t("settings.gateways.webhookLabel")}>
                  <CopyableValue value={webhookUrl} />
                </Field>
              )}
              {flagFields.map((field) => (
                <div key={field.key} className="flex items-center gap-3">
                  <div className="min-w-0 flex-1">
                    <p className="text-[13px] font-medium text-foreground">
                      {t(`settings.gateways.fields.${gateway.type}.${field.key}`)}
                    </p>
                    <p className="text-[12px] text-muted-foreground">
                      {t(`settings.gateways.flagHints.${field.key}`)}
                    </p>
                  </div>
                  <div className="mr-1 flex">
                    <Switch
                      checked={gateway.flags[field.key] ?? false}
                      onChange={(enabled) => void handleFlag(field.key, enabled)}
                      disabled={savingFlag === field.key}
                    />
                  </div>
                </div>
              ))}
              {valueFields.map((field) => {
                // once configured, a blank field keeps the stored value
                const mustFill = field.required && !gateway.is_configured;
                return (
                  <Field
                    key={field.key}
                    label={t(`settings.gateways.fields.${gateway.type}.${field.key}`)}
                    htmlFor={`gateway-${gateway.type}-${field.key}`}
                    aside={mustFill ? <span className="text-error">*</span> : undefined}
                  >
                    <TextInput
                      id={`gateway-${gateway.type}-${field.key}`}
                      required={mustFill}
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
                    />
                  </Field>
                );
              })}
              {(valueFields.length > 0 || canTest) && (
                <div className="flex flex-wrap gap-2">
                  {valueFields.length > 0 && (
                    <Button
                      variant="accent"
                      className="w-fit"
                      type="submit"
                      disabled={isSubmitting}
                    >
                      {isSubmitting ? t("settings.gateways.saving") : t("settings.gateways.save")}
                    </Button>
                  )}
                  {canTest && (
                    <Button
                      variant="outline"
                      className="w-fit"
                      onClick={() => void handleTestPayment()}
                      disabled={isTesting}
                    >
                      {isTesting
                        ? t("settings.gateways.testPaymentCreating")
                        : t("settings.gateways.testPayment")}
                    </Button>
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
