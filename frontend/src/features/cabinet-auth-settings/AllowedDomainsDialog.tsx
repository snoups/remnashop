import { MailCheck } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { updateCabinetAuthSettings, type CabinetAuthSettings } from "@entities/settings/api";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { Button } from "@shared/ui/Button";
import { ChipsInput } from "@shared/ui/ChipsInput";
import { GLASS_DIALOG_FOOTER_CLASS } from "@shared/ui/classes";
import { DialogHeader } from "@shared/ui/glass/DialogHeader";
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
      <DialogHeader icon={MailCheck} title={t("settings.cabinetAuth.allowedDomains")} />

      <form onSubmit={(event) => void handleSubmit(event)} className="flex min-h-0 flex-1 flex-col">
        <div className="flex flex-col gap-1.5 p-4">
          <ChipsInput values={values} onChange={setValues} normalize={normalizeDomain} placeholder="example.com" />
          <span className="text-[12px] text-muted-foreground">{t("settings.cabinetAuth.allowedDomainsHint")}</span>
        </div>
        {canManage && (
          <div className={`${GLASS_DIALOG_FOOTER_CLASS} shrink-0 justify-end`}>
            <Button variant="glass" onClick={close}>
              {t("common.cancel")}
            </Button>
            <Button variant="glassAccent" type="submit" isLoading={isSubmitting}>
              {t("common.save")}
            </Button>
          </div>
        )}
      </form>
    </>
  );
}
