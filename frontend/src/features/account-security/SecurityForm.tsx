import { Lock, Plus } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { getOwnSecurity, updateOwnSecurity } from "@entities/user/security";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { ErrorState } from "@shared/ui/EmptyState";
import { Spinner } from "@shared/ui/Spinner";
import { Button } from "@shared/ui/Button";
import { TextArea } from "@shared/ui/TextInput";
import { Card } from "@shared/ui/Card";
import { CardHeader } from "@shared/ui/CardHeader";

const IPV4_PATTERN = /^(\d{1,3}\.){3}\d{1,3}$/;

/** Mirrors the backend's ipaddress.ip_network(entry, strict=False): an address, optionally with a prefix. */
function isIpOrNetwork(entry: string): boolean {
  const [address, prefix, ...rest] = entry.split("/");
  if (rest.length > 0) return false;
  const isV6 = address.includes(":");
  if (prefix !== undefined && !(/^\d{1,3}$/.test(prefix) && Number(prefix) <= (isV6 ? 128 : 32))) return false;
  try {
    // the URL parser validates IPv6 and rejects octets over 255; a hostname that
    // comes back changed means leading zeros or a shorthand like "10.1"
    if (isV6) return Boolean(new URL(`http://[${address}]`).hostname);
    return IPV4_PATTERN.test(address) && new URL(`http://${address}`).hostname === address;
  } catch {
    return false;
  }
}

function parseEntries(text: string): string[] {
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

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
    <Card>
      <CardHeader
        icon={Lock}
        title={t("profile.accountSecurity.title")}
        description={t("profile.accountSecurity.description")}
      />

      {state.kind === "loading" && (
        <Spinner size="card" />
      )}
      {state.kind === "error" && (
        <ErrorState text={t("profile.accountSecurity.loadError")} />
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
            aria-invalid={invalidEntries.length > 0}
          />
          {invalidEntries.length > 0 && (
            <p className="mt-1.5 text-[12px] text-error">
              {t("profile.accountSecurity.invalidEntries", { entries: invalidEntries.join(", ") })}
            </p>
          )}
          {clientIp && (
            <div className="mt-2 flex items-center gap-2 text-[12px] text-muted-foreground">
              <span>{t("profile.accountSecurity.currentIp", { ip: clientIp })}</span>
              {!entries.includes(clientIp) && (
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setText(entries.concat(clientIp).join("\n"))}
                >
                  <Plus className="size-3.5" />
                  {t("common.add")}
                </Button>
              )}
            </div>
          )}
          <Button
            variant="outline"
            className="mt-3"
            type="submit"
            disabled={isSaving || invalidEntries.length > 0}
          >
            {t("common.save")}
          </Button>
        </form>
      )}
    </Card>
  );
}
