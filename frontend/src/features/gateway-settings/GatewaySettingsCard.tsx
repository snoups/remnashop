import type { ParseKeys } from "i18next";
import { BookOpen } from "lucide-react";
import { useEffect, useState, type ChangeEvent, type FormEvent } from "react";
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
import { usePermissions } from "@entities/user/use-current-user";
import { getErrorMessage } from "@shared/api/http";
import { isHttpsUrl } from "@shared/lib/external-links";
import { toast } from "@shared/lib/toast";
import { Button } from "@shared/ui/Button";
import { Field } from "@shared/ui/glass/Field";
import { CopyInput, Input, PasswordInput } from "@shared/ui/glass/Input";
import { Row } from "@shared/ui/glass/Row";
import { Switch } from "@shared/ui/glass/Switch";
import { Pressable } from "@shared/ui/Pressable";
import { SaveFooter } from "@shared/ui/SaveFooter";

import { GATEWAY_DOCS_URLS } from "./docs-links";
import { GATEWAY_LOGOS } from "./logos";
import { inputModeFor, sanitizeFieldValue } from "./field-input";

const CURRENCY_HINT_GATEWAYS = new Set([
  "CRYPTOMUS",
  "HELEKET",
  "CRYPTOPAY",
  "WATA",
  "VALUTIX",
  "RIOPAY",
  "SEVERPAY",
  "CLOUDPAYMENTS",
  "PAYPALYCH",
]);

const TEST_PAYMENT_POLL_MS = 3000;

interface GatewaySettingsCardProps {
  gateway: Gateway;
  fields: GatewayFieldSpec[];
  webhookUrl: string | null;
  onChanged: (gateway: Gateway) => void;
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

  const label = t(`settings.gateways.types.${gateway.type}` as ParseKeys);
  const flagFields = fields.filter((field) => field.kind === "boolean");
  const valueFields = fields.filter((field) => field.kind !== "boolean");
  const docsUrl = GATEWAY_DOCS_URLS[gateway.type];
  const logoUrl = GATEWAY_LOGOS[gateway.type];
  const canExpand = fields.length > 0 || webhookUrl !== null;
  const dirty = Object.values(values).some((value) => value !== "");
  // Stars pays inside the bot, there is no provider page to open
  const permissions = usePermissions();
  const canUpdate = permissions.includes("GATEWAYS_UPDATE");
  const canTest =
    gateway.is_configured && gateway.type !== "TELEGRAM_STARS" && permissions.includes("GATEWAYS_TEST");

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const changed = Object.fromEntries(Object.entries(values).filter(([, value]) => value !== ""));
    if (Object.keys(changed).length === 0) return;

    setIsSubmitting(true);
    try {
      onChanged(await updateGatewaySettings(gateway.type, changed));
      setValues({});
      toast.success(t("common.saved"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleFlag = async (key: string, enabled: boolean) => {
    setSavingFlag(key);
    try {
      onChanged(await updateGatewaySettings(gateway.type, { [key]: String(enabled) }));
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
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
      if (document.hidden) return;
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

  const testButton = canTest && (
    <Button variant="glass" isLoading={isTesting} onClick={() => void handleTestPayment()}>
      {isTesting ? t("settings.gateways.testPaymentCreating") : t("settings.gateways.testPayment")}
    </Button>
  );

  return (
    <Row
      glyph={
        logoUrl ? (
          <img src={logoUrl} alt="" className="size-[22px] rounded-[6px] object-contain" />
        ) : (
          <span className="text-[13px] font-semibold">{label.charAt(0)}</span>
        )
      }
      label={label}
      description={
        <span className={`flex items-center gap-1.5 ${gateway.is_configured ? "text-success" : "text-warning"}`}>
          <span className="size-1.5 rounded-full bg-current" />
          {t(gateway.is_configured ? "settings.gateways.configured" : "settings.gateways.notConfigured")}
        </span>
      }
      expanded={canExpand ? isOpen : undefined}
      onClick={canExpand ? () => setIsOpen((open) => !open) : undefined}
      onSubmit={(event) => void handleSubmit(event)}
      panel={
        canExpand && (
          <>
            {webhookUrl !== null && (
              <Field label={t("settings.gateways.webhookLabel")} htmlFor={`gateway-${gateway.type}-webhook`}>
                <CopyInput id={`gateway-${gateway.type}-webhook`} value={webhookUrl} />
              </Field>
            )}
            {flagFields.map((field) => (
              // 2px past the panel's 14px: the switch under the row's own (16px in)
              <div key={field.key} className="flex items-center gap-3 pr-0.5">
                <div className="min-w-0 flex-1">
                  <p className="text-[13px] font-medium text-foreground">
                    {t(`settings.gateways.fields.${field.key}` as ParseKeys)}
                  </p>
                  <p className="text-[12px] text-muted-foreground">
                    {t(`settings.gateways.flagHints.${field.key}` as ParseKeys)}
                  </p>
                </div>
                <Switch
                  checked={gateway.flags[field.key] ?? false}
                  onChange={(enabled) => void handleFlag(field.key, enabled)}
                  disabled={!canUpdate || savingFlag === field.key}
                />
              </div>
            ))}
            {valueFields.map((field) => {
              // once configured, a blank field keeps the stored value
              const mustFill = field.required && !gateway.is_configured;
              const inputProps = {
                id: `gateway-${gateway.type}-${field.key}`,
                inputMode: inputModeFor(field),
                value: values[field.key] ?? "",
                onChange: (event: ChangeEvent<HTMLInputElement>) =>
                  setValues((prev) => ({
                    ...prev,
                    [field.key]: sanitizeFieldValue(field, event.target.value),
                  })),
                placeholder: t("settings.gateways.placeholder"),
                disabled: !canUpdate,
              };
              return (
                <Field
                  key={field.key}
                  label={t(`settings.gateways.fields.${field.key}` as ParseKeys)}
                  htmlFor={inputProps.id}
                  required={mustFill}
                  info={
                    field.key === "currency" && CURRENCY_HINT_GATEWAYS.has(gateway.type)
                      ? t(`settings.gateways.currencyHints.${gateway.type}` as ParseKeys)
                      : undefined
                  }
                >
                  {field.kind === "secret" ? (
                    // "off" is ignored on password fields: the browser would offer the admin's saved password
                    <PasswordInput {...inputProps} autoComplete="new-password" />
                  ) : (
                    <Input {...inputProps} autoComplete="off" />
                  )}
                </Field>
              );
            })}
            {valueFields.length > 0 && canUpdate ? (
              <SaveFooter flush dirty={dirty} saving={isSubmitting} beside={testButton} />
            ) : (
              testButton && <div className="flex items-center gap-3">{testButton}</div>
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
          </>
        )
      }
    >
      {docsUrl && (
        <Pressable
          as="a"
          href={docsUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="flex size-8 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-white/[0.06] hover:text-foreground"
        >
          <BookOpen className="size-3.5" />
        </Pressable>
      )}
      <Switch
        checked={gateway.is_active}
        onChange={() => void handleToggle()}
        disabled={!permissions.includes("GATEWAYS_ACTIVE_SET") || isToggling || !gateway.is_configured}
      />
    </Row>
  );
}
