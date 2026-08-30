import { Lock } from "lucide-react";
import { motion } from "motion/react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { getOwnSecurity, updateOwnSecurity } from "@entities/user/security";
import { getErrorMessage } from "@shared/api/http";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";

export function SecurityForm() {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
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
    <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-5">
      <div className="flex items-center gap-2.5">
        <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] text-foreground backdrop-blur-md">
          <Lock className="size-4" />
        </div>
        <div>
          <h2 className="text-sm font-bold text-foreground">{t("profile.accountSecurity.title")}</h2>
          <p className="text-[12.5px] text-muted-foreground">{t("profile.accountSecurity.description")}</p>
        </div>
      </div>

      {state.kind === "loading" && (
        <p className="mt-4 text-sm text-muted-foreground">{t("profile.accountSecurity.loading")}</p>
      )}
      {state.kind === "error" && (
        <p className="mt-4 text-sm text-error">{t("profile.accountSecurity.loadError")}</p>
      )}
      {state.kind === "ready" && (
        <form onSubmit={(event) => void handleSubmit(event)} className="mt-4">
          <textarea
            value={text}
            onChange={(event) => setText(event.target.value)}
            placeholder={t("profile.accountSecurity.placeholder")}
            rows={4}
            className="w-full min-h-[38px] rounded-xl border border-border bg-input px-3 py-2 text-sm text-foreground"
          />
          <motion.button
            type="submit"
            {...bounceTap(bounceStrength)}
            className="mt-2 rounded-full border border-border px-3 py-1.5 text-sm text-foreground/90 transition-colors hover:bg-white/5"
          >
            {t("profile.accountSecurity.submit")}
          </motion.button>
        </form>
      )}
    </div>
  );
}
