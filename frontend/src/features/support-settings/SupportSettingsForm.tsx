import { LifeBuoy } from "lucide-react";
import { useEffect, useId, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { getShopSettings, updateShopSettings } from "@entities/settings/api";
import { usePermissions } from "@entities/user/use-current-user";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { useFieldValidation } from "@shared/lib/use-field-validation";
import { ErrorState } from "@shared/ui/glass/EmptyState";
import { Field } from "@shared/ui/glass/Field";
import { Input } from "@shared/ui/glass/Input";
import { Section, SectionFields } from "@shared/ui/glass/Section";
import { SaveFooter } from "@shared/ui/SaveFooter";
import { Spinner } from "@shared/ui/Spinner";

// what the backend takes for the support chat: "name", "@name", "t.me/name" or "https://t.me/name"
const SUPPORT_TELEGRAM = /^(?:@|(?:https?:\/\/)?t\.me\/)?[A-Za-z0-9_]{4,32}\/?$/;

/** Where the bot's and the cabinet's "Support" leads: a Telegram chat, a web page, or both.
 *  Shop settings underneath, saved on their own (a partial PATCH). */
export function SupportSettingsForm() {
  const { t } = useTranslation();
  const canManage = usePermissions().includes("SHOP_SETTINGS_MANAGE");
  const [state, , setData] = useAsyncResource(getShopSettings);
  const [telegram, setTelegram] = useState("");
  const [url, setUrl] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const id = useId();
  const validation = useFieldValidation<"telegram" | "url">();

  useEffect(() => {
    if (state.kind !== "ready") return;
    setTelegram(state.data.support_telegram ?? "");
    setUrl(state.data.support_url ?? "");
  }, [state]);

  const errors = {
    telegram:
      telegram.trim() !== "" && !SUPPORT_TELEGRAM.test(telegram.trim()) ? t("settings.shop.supportTelegramInvalid") : null,
    url: url.trim() !== "" && !url.trim().startsWith("https://") ? t("settings.shop.supportUrlInvalid") : null,
  };
  const shown = (name: keyof typeof errors) => validation.visible(name, errors[name]);
  const watch = (name: keyof typeof errors) => ({
    onBlur: validation.touch(name),
    "aria-invalid": shown(name) !== undefined,
  });

  const saved = state.kind === "ready" ? state.data : null;
  const dirty = saved !== null && (telegram !== (saved.support_telegram ?? "") || url !== (saved.support_url ?? ""));

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    validation.submit();
    if (errors.telegram !== null || errors.url !== null) return;
    setIsSubmitting(true);
    try {
      // blank clears it; the backend takes "@name" and t.me links as well
      setData(await updateShopSettings({ support_telegram: telegram.trim() || null, support_url: url.trim() || null }));
      validation.reset();
      toast.success(t("common.saved"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <form onSubmit={(event) => void handleSubmit(event)}>
      <Section
        icon={LifeBuoy}
        title={t("settings.support.title")}
        description={t("settings.support.description")}
        footer={state.kind === "ready" && canManage && <SaveFooter dirty={dirty} saving={isSubmitting} />}
      >
        {state.kind === "loading" && <Spinner size="card" />}
        {state.kind === "error" && <ErrorState text={t("common.loadError")} />}
        {state.kind === "ready" && (
          <fieldset disabled={!canManage} className="contents">
            <SectionFields>
              <Field label={t("settings.shop.supportTelegramLabel")} htmlFor={`${id}-telegram`} error={shown("telegram")}>
                <Input
                  id={`${id}-telegram`}
                  placeholder={t("settings.shop.supportTelegramPlaceholder")}
                  value={telegram}
                  onChange={(event) => setTelegram(event.target.value)}
                  autoComplete="off"
                  {...watch("telegram")}
                />
              </Field>
              <Field label={t("settings.shop.supportUrlLabel")} htmlFor={`${id}-url`} error={shown("url")}>
                <Input
                  id={`${id}-url`}
                  placeholder={t("settings.shop.supportUrlPlaceholder")}
                  value={url}
                  onChange={(event) => setUrl(event.target.value)}
                  autoComplete="off"
                  {...watch("url")}
                />
              </Field>
            </SectionFields>
          </fieldset>
        )}
      </Section>
    </form>
  );
}
