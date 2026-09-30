import { Lock } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { getOwnSecurity, updateOwnSecurity } from "@entities/user/security";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { Spinner } from "@shared/ui/Spinner";
import { Button } from "@shared/ui/Button";
import { TextArea } from "@shared/ui/TextInput";
import { Card } from "@shared/ui/Card";

export function SecurityForm() {
  const { t } = useTranslation();
  const [text, setText] = useState("");
  const [state] = useAsyncResource(getOwnSecurity, (settings) =>
    setText(settings.ip_allowlist.join("\n")),
  );

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const entries = text
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);
    try {
      await updateOwnSecurity(entries);
    } catch (err) {
      toast.error(getErrorMessage(err, t("profile.accountSecurity.saveError")));
    }
  };

  return (
    <Card>
      <div className="flex items-center gap-2.5">
        <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] text-foreground backdrop-blur-md">
          <Lock className="size-4" />
        </div>
        <div>
          <h2 className="text-sm font-bold text-foreground">{t("profile.accountSecurity.title")}</h2>
          <p className="mt-0.5 text-[12.5px] text-muted-foreground">{t("profile.accountSecurity.description")}</p>
        </div>
      </div>

      <div className="-mx-4 mt-4 border-t border-white/[0.07]" />

      {state.kind === "loading" && (
        <Spinner size="card" />
      )}
      {state.kind === "error" && (
        <p className="mt-4 text-sm text-error">{t("profile.accountSecurity.loadError")}</p>
      )}
      {state.kind === "ready" && (
        <form onSubmit={(event) => void handleSubmit(event)} className="mt-4">
          <TextArea
            value={text}
            onChange={(event) => setText(event.target.value)}
            placeholder={t("profile.accountSecurity.placeholder")}
            spellCheck={false}
            rows={4}
            className="w-full"
          />
          <Button
            variant="outline"
            className="mt-2"
            type="submit"
          >
            {t("profile.accountSecurity.submit")}
          </Button>
        </form>
      )}
    </Card>
  );
}
