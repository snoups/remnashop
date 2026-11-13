import { useEffect, useId, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { getShopSettings, updateShopSettings } from "@entities/settings/api";
import { usePermissions } from "@entities/user/use-current-user";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { Button } from "@shared/ui/Button";
import { Field } from "@shared/ui/glass/Field";
import { Input } from "@shared/ui/glass/Input";
import { SectionFields } from "@shared/ui/glass/Section";

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/** The shop's own email for every gateway, so customers aren't asked for theirs. */
export function PaymentEmailField() {
  const { t } = useTranslation();
  const canManage = usePermissions().includes("SHOP_SETTINGS_MANAGE");
  const [state, , setData] = useAsyncResource(getShopSettings);
  const [email, setEmail] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const id = useId();

  useEffect(() => {
    if (state.kind === "ready") setEmail(state.data.payment_email ?? "");
  }, [state]);

  if (state.kind !== "ready") return null;

  const value = email.trim();
  const error = value !== "" && !EMAIL.test(value) ? t("settings.gateways.paymentEmailInvalid") : undefined;
  const dirty = value !== (state.data.payment_email ?? "");

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (error) return;
    setIsSubmitting(true);
    try {
      setData(await updateShopSettings({ payment_email: value || null }));
      toast.success(t("common.saved"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <form onSubmit={(event) => void handleSubmit(event)}>
      <fieldset disabled={!canManage} className="contents">
        <SectionFields>
          <Field
            label={t("settings.gateways.paymentEmailLabel")}
            htmlFor={id}
            hint={t("settings.gateways.paymentEmailHint")}
            error={error}
          >
            <div className="flex gap-2">
              <Input
                id={id}
                type="email"
                className="min-w-0 flex-1"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                autoComplete="off"
                aria-invalid={error !== undefined}
              />
              {canManage && (
                <Button variant="secondary" size="md" type="submit" disabled={!dirty || isSubmitting}>
                  {t("common.save")}
                </Button>
              )}
            </div>
          </Field>
        </SectionFields>
      </fieldset>
    </form>
  );
}
