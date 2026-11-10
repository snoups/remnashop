import { Lock, Plus } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { getOwnSecurity, isIpCovered, isIpOrNetwork, parseEntries, updateOwnSecurity } from "@entities/user/security";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { ErrorState } from "@shared/ui/glass/EmptyState";
import { TextArea } from "@shared/ui/glass/Input";
import { Section, SectionFields } from "@shared/ui/glass/Section";
import { Spinner } from "@shared/ui/Spinner";
import { Button } from "@shared/ui/Button";
import { SaveFooter } from "@shared/ui/SaveFooter";

export function SecurityForm() {
  const { t } = useTranslation();
  const [text, setText] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [state, , setSettings] = useAsyncResource(getOwnSecurity, {
    onSuccess: (settings) => setText(settings.ip_allowlist.join("\n")),
  });

  const entries = parseEntries(text);
  const invalidEntries = entries.filter((entry) => !isIpOrNetwork(entry));
  const clientIp = state.kind === "ready" ? state.data.client_ip : null;
  const dirty = state.kind === "ready" && entries.join("\n") !== state.data.ip_allowlist.join("\n");

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setIsSaving(true);
    try {
      const updated = await updateOwnSecurity(entries);
      setSettings(updated);
      setText(updated.ip_allowlist.join("\n"));
      toast.success(t("profile.accountSecurity.saved"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("profile.accountSecurity.saveError")));
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <form onSubmit={(event) => void handleSubmit(event)}>
      <Section
        icon={Lock}
        title={t("profile.accountSecurity.title")}
        description={t("profile.accountSecurity.description")}
        footer={
          state.kind === "ready" && (
            <SaveFooter dirty={dirty} saving={isSaving} disabled={invalidEntries.length > 0} />
          )
        }
      >
        {state.kind === "loading" && <Spinner size="card" />}
        {state.kind === "error" && <ErrorState text={t("common.loadError")} />}
        {state.kind === "ready" && (
          <SectionFields>
            <TextArea
              value={text}
              onChange={(event) => setText(event.target.value)}
              placeholder={t("profile.accountSecurity.placeholder")}
              spellCheck={false}
              rows={4}
              mono
              aria-invalid={invalidEntries.length > 0}
            />
            {invalidEntries.length > 0 && (
              <p className="text-xs text-error">
                {t("profile.accountSecurity.invalidEntries", { entries: invalidEntries.join(", ") })}
              </p>
            )}
            {clientIp && (
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <span>{t("profile.accountSecurity.currentIp", { ip: clientIp })}</span>
                {!isIpCovered(clientIp, entries) && (
                  <Button variant="glass" size="sm" icon={Plus} onClick={() => setText(entries.concat(clientIp).join("\n"))}>
                    {t("common.add")}
                  </Button>
                )}
              </div>
            )}
          </SectionFields>
        )}
      </Section>
    </form>
  );
}
