import { MailX } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { updateCabinetAuthSettings, type CabinetAuthSettings } from "@entities/settings/api";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { Button } from "@shared/ui/Button";
import { ChipsInput } from "@shared/ui/ChipsInput";
import { DialogHeader } from "@shared/ui/DialogHeader";
import { Modal } from "@shared/ui/Modal";
import { useModalClose } from "@shared/ui/modal-hooks";

const DOMAIN_PATTERN = /^[a-z0-9-]+(\.[a-z0-9-]+)+$/;

function normalizeDomain(token: string): string | null {
  const domain = token.trim().toLowerCase().replace(/^@/, "");
  return DOMAIN_PATTERN.test(domain) ? domain : null;
}

interface AllowedDomainsDialogProps {
  domains: string[];
  canManage: boolean;
  onSaved: (settings: CabinetAuthSettings) => void;
  onClose: () => void;
}

export function AllowedDomainsDialog({ onClose, ...props }: AllowedDomainsDialogProps) {
  return (
    <Modal onClose={onClose} size="lg">
      <AllowedDomainsForm {...props} />
    </Modal>
  );
}

function AllowedDomainsForm({ domains, canManage, onSaved }: Omit<AllowedDomainsDialogProps, "onClose">) {
  const { t } = useTranslation();
  const close = useModalClose();
  const [values, setValues] = useState(domains);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setIsSubmitting(true);
    try {
      onSaved(await updateCabinetAuthSettings({ allowed_email_domains: values }));
      toast.success(t("common.saved"));
      close();
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
      setIsSubmitting(false);
    }
  };

  return (
    <>
      <DialogHeader icon={MailX} title={t("settings.cabinetAuth.allowedDomains")} />

      <form onSubmit={(event) => void handleSubmit(event)} className="flex min-h-0 flex-1 flex-col">
        <div className="flex flex-col gap-3 p-4">
          <div className="flex flex-col gap-1">
            <ChipsInput values={values} onChange={setValues} normalize={normalizeDomain} placeholder="example.com" />
            <span className="text-[12px] text-muted-foreground">{t("settings.cabinetAuth.allowedDomainsHint")}</span>
          </div>
          {canManage && (
            <div className="flex justify-end gap-2">
              <Button variant="outline" type="button" onClick={close}>
                {t("common.cancel")}
              </Button>
              <Button variant="accent" type="submit" disabled={isSubmitting}>
                {isSubmitting ? t("common.saving") : t("common.save")}
              </Button>
            </div>
          )}
        </div>
      </form>
    </>
  );
}
