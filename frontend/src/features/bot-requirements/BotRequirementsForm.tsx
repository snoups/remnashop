import { ClipboardCheck } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { getBotRequirements, updateBotRequirements } from "@entities/settings/api";
import { usePermissions } from "@entities/user/use-current-user";
import { ApiError, getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { Button } from "@shared/ui/Button";
import { Card } from "@shared/ui/Card";
import { CardHeader } from "@shared/ui/CardHeader";
import { ErrorState } from "@shared/ui/EmptyState";
import { Field } from "@shared/ui/Field";
import { Spinner } from "@shared/ui/Spinner";
import { Switch } from "@shared/ui/Switch";
import { TextInput } from "@shared/ui/TextInput";

const CHANNEL_ID_PATTERN = /^-?\d+$/;

const blankToNull = (value: string): string | null => (value.trim() === "" ? null : value.trim());

export function BotRequirementsForm() {
  const { t } = useTranslation();
  const canManage = usePermissions().includes("BOT_REQUIREMENTS_MANAGE");
  const [state, , setData] = useAsyncResource(getBotRequirements);
  const [rulesRequired, setRulesRequired] = useState(false);
  const [rulesUrl, setRulesUrl] = useState("");
  const [channelRequired, setChannelRequired] = useState(false);
  const [channelId, setChannelId] = useState("");
  const [channelUrl, setChannelUrl] = useState("");
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (state.kind !== "ready") return;
    setRulesRequired(state.data.rules_required);
    setRulesUrl(state.data.rules_url ?? "");
    setChannelRequired(state.data.channel_required);
    setChannelId(state.data.channel_id === null ? "" : String(state.data.channel_id));
    setChannelUrl(state.data.channel_url ?? "");
  }, [state]);

  const channelIdValid = channelId.trim() === "" || CHANNEL_ID_PATTERN.test(channelId.trim());

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!channelIdValid) {
      toast.error(t("common.errors.generic"));
      return;
    }
    const parsedChannelId = channelId.trim() === "" ? null : Number.parseInt(channelId, 10);
    setIsSubmitting(true);
    setErrorCode(null);
    try {
      const requirements = await updateBotRequirements({
        rules_required: rulesRequired,
        rules_url: blankToNull(rulesUrl),
        channel_required: channelRequired,
        channel_id: parsedChannelId,
        channel_url: blankToNull(channelUrl),
      });
      setData(requirements);
      toast.success(t("common.saved"));
    } catch (err) {
      if (err instanceof ApiError) setErrorCode(err.code);
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    } finally {
      setIsSubmitting(false);
    }
  };

  const incomplete = errorCode === "BOT_REQUIREMENTS_INCOMPLETE";
  const channelInaccessible = errorCode === "CHANNEL_NOT_ACCESSIBLE";

  return (
    <Card>
      <CardHeader
        icon={ClipboardCheck}
        title={t("settings.botRequirements.title")}
        description={t("settings.botRequirements.description")}
      />

      {state.kind === "loading" && <Spinner size="card" />}
      {state.kind === "error" && <ErrorState text={t("settings.botRequirements.loadError")} />}
      {state.kind === "ready" && (
        <form onSubmit={(event) => void handleSubmit(event)} className="mt-4 flex flex-col gap-4">
          <fieldset disabled={!canManage} className="flex flex-col gap-4">
            <div className="flex flex-col gap-3">
              <div className="flex items-center justify-between gap-3 px-[12.5px]">
                <p className="text-[13px] font-medium text-foreground">
                  {t("settings.botRequirements.rulesLabel")}
                </p>
                <Switch checked={rulesRequired} onChange={setRulesRequired} />
              </div>
              <Field label={t("settings.botRequirements.rulesUrl")}>
                <TextInput
                  type="url"
                  value={rulesUrl}
                  onChange={(event) => setRulesUrl(event.target.value)}
                  disabled={!rulesRequired}
                  aria-invalid={incomplete && rulesRequired && rulesUrl.trim() === ""}
                />
              </Field>
            </div>

            <div className="flex flex-col gap-3 border-t border-white/[0.08] pt-4">
              <div className="flex items-center justify-between gap-3 px-[12.5px]">
                <p className="text-[13px] font-medium text-foreground">
                  {t("settings.botRequirements.channelLabel")}
                </p>
                <Switch checked={channelRequired} onChange={setChannelRequired} />
              </div>
              <Field label={t("settings.botRequirements.channelId")}>
                <TextInput
                  type="text"
                  inputMode="numeric"
                  value={channelId}
                  onChange={(event) => setChannelId(event.target.value)}
                  disabled={!channelRequired}
                  aria-invalid={(incomplete && channelRequired && channelId.trim() === "") || channelInaccessible || !channelIdValid}
                />
              </Field>
              <Field label={t("settings.botRequirements.channelUrl")}>
                <TextInput
                  type="url"
                  value={channelUrl}
                  onChange={(event) => setChannelUrl(event.target.value)}
                  disabled={!channelRequired}
                  aria-invalid={incomplete && channelRequired && channelUrl.trim() === ""}
                />
              </Field>
            </div>
          </fieldset>

          {canManage && (
            <Button variant="accent" className="w-fit" type="submit" disabled={isSubmitting}>
              {isSubmitting ? t("common.saving") : t("common.save")}
            </Button>
          )}
        </form>
      )}
    </Card>
  );
}
