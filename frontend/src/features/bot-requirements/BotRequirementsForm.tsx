import { ClipboardCheck, Gift, Megaphone } from "lucide-react";
import { useEffect, useId, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { getBotRequirements, updateBotRequirements } from "@entities/settings/api";
import { usePermissions } from "@entities/user/use-current-user";
import { ApiError, getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { useFieldValidation } from "@shared/lib/use-field-validation";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { ErrorState } from "@shared/ui/glass/EmptyState";
import { Field } from "@shared/ui/glass/Field";
import { Input } from "@shared/ui/glass/Input";
import { Row } from "@shared/ui/glass/Row";
import { Section, SectionFields, SectionRows } from "@shared/ui/glass/Section";
import { Switch } from "@shared/ui/glass/Switch";
import { SaveFooter } from "@shared/ui/SaveFooter";
import { Spinner } from "@shared/ui/Spinner";

const CHANNEL_ID_PATTERN = /^-?\d+$/;

const blankToNull = (value: string): string | null => (value.trim() === "" ? null : value.trim());

// the channel button opens Telegram; the backend checks the same domains
const TELEGRAM_LINK_HOSTS: ReadonlySet<string> = new Set(["t.me", "telegram.me", "telegram.dog"]);

// "t.me/name" as copied from Telegram: the scheme is implied
function withScheme(value: string): string {
  const trimmed = value.trim();
  return trimmed === "" || trimmed.includes("://") ? trimmed : `https://${trimmed}`;
}

function isTelegramLink(value: string): boolean {
  try {
    const url = new URL(value);
    return (url.protocol === "https:" || url.protocol === "http:") && TELEGRAM_LINK_HOSTS.has(url.hostname.toLowerCase());
  } catch {
    return false;
  }
}

export function BotRequirementsForm() {
  const { t } = useTranslation();
  const canManage = usePermissions().includes("BOT_REQUIREMENTS_MANAGE");
  const [state, , setData] = useAsyncResource(getBotRequirements);
  const [channelRequired, setChannelRequired] = useState(false);
  const [channelId, setChannelId] = useState("");
  const [channelUrl, setChannelUrl] = useState("");
  const [trialChannelGuard, setTrialChannelGuard] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const id = useId();

  useEffect(() => {
    if (state.kind !== "ready") return;
    setChannelRequired(state.data.channel_required);
    setChannelId(state.data.channel_id === null ? "" : String(state.data.channel_id));
    setChannelUrl(state.data.channel_url ?? "");
    setTrialChannelGuard(state.data.trial_channel_guard);
  }, [state]);

  const validation = useFieldValidation<"channelId" | "channelUrl">();
  const normalizedUrl = withScheme(channelUrl);
  // only a required channel needs its id and link
  const channelIdError = !channelRequired
    ? null
    : channelId.trim() === ""
      ? t("errors.validation.required")
      : !CHANNEL_ID_PATTERN.test(channelId.trim())
        ? t("settings.botRequirements.channelIdInvalid")
        : null;
  const channelUrlError = !channelRequired
    ? null
    : normalizedUrl === ""
      ? t("errors.validation.required")
      : !isTelegramLink(normalizedUrl)
        ? t("settings.botRequirements.channelUrlInvalid")
        : null;
  const hasErrors = channelIdError !== null || channelUrlError !== null;
  const channelIdShown = validation.visible("channelId", channelIdError);
  const channelUrlShown = validation.visible("channelUrl", channelUrlError);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    validation.submit();
    if (hasErrors) return;
    const parsedChannelId = channelId.trim() === "" ? null : Number.parseInt(channelId, 10);
    setIsSubmitting(true);
    try {
      const requirements = await updateBotRequirements({
        channel_required: channelRequired,
        channel_id: parsedChannelId,
        channel_url: blankToNull(normalizedUrl),
        trial_channel_guard: trialChannelGuard,
      });
      setData(requirements);
      validation.reset();
      toast.success(t("common.saved"));
    } catch (err) {
      // the bot can't see the channel: said under the id, where it's fixed
      if (err instanceof ApiError && err.code === "CHANNEL_NOT_ACCESSIBLE") {
        validation.setServerError("channelId", getErrorMessage(err, t("common.errors.generic")));
      } else {
        toast.error(getErrorMessage(err, t("common.errors.generic")));
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const saved = state.kind === "ready" ? state.data : null;
  const dirty =
    saved !== null &&
    (channelRequired !== saved.channel_required ||
      channelId !== (saved.channel_id === null ? "" : String(saved.channel_id)) ||
      channelUrl !== (saved.channel_url ?? "") ||
      trialChannelGuard !== saved.trial_channel_guard);

  return (
    <form onSubmit={(event) => void handleSubmit(event)}>
      <Section
        icon={ClipboardCheck}
        title={t("settings.botRequirements.title")}
        description={t("settings.botRequirements.description")}
        footer={
          state.kind === "ready" &&
          // stays enabled with errors: pressing it shows them all instead of sending
          canManage && <SaveFooter dirty={dirty} saving={isSubmitting} />
        }
      >
        {state.kind === "loading" && <Spinner size="card" />}
        {state.kind === "error" && <ErrorState text={t("common.loadError")} />}
        {state.kind === "ready" && (
          <fieldset disabled={!canManage} className="contents">
            <SectionRows>
              <Row
                icon={Megaphone}
                label={t("settings.botRequirements.channelLabel")}
                description={t("settings.botRequirements.channelHint")}
              >
                <Switch checked={channelRequired} onChange={setChannelRequired} />
              </Row>
              <Row
                icon={Gift}
                label={t("settings.botRequirements.trialChannelGuard")}
                description={t("settings.botRequirements.trialChannelGuardHint")}
              >
                <Switch checked={trialChannelGuard} onChange={setTrialChannelGuard} disabled={!channelRequired} />
              </Row>
            </SectionRows>
            <SectionFields divided>
              <Field label={t("settings.botRequirements.channelId")} htmlFor={`${id}-channel-id`} error={channelIdShown}>
                <Input
                  id={`${id}-channel-id`}
                  type="text"
                  inputMode="numeric"
                  value={channelId}
                  onChange={(event) => {
                    setChannelId(event.target.value);
                    validation.changed("channelId");
                  }}
                  onBlur={validation.touch("channelId")}
                  disabled={!channelRequired}
                  aria-invalid={channelIdShown !== undefined}
                />
              </Field>
              <Field label={t("settings.botRequirements.channelUrl")} htmlFor={`${id}-channel-url`} error={channelUrlShown}>
                {/* text, not url: the browser would refuse "t.me/name" without a scheme */}
                <Input
                  id={`${id}-channel-url`}
                  type="text"
                  inputMode="url"
                  placeholder={t("settings.botRequirements.channelUrlPlaceholder")}
                  value={channelUrl}
                  onChange={(event) => setChannelUrl(event.target.value)}
                  onBlur={validation.touch("channelUrl")}
                  disabled={!channelRequired}
                  aria-invalid={channelUrlShown !== undefined}
                />
              </Field>
            </SectionFields>
          </fieldset>
        )}
      </Section>
    </form>
  );
}
