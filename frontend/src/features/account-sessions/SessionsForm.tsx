import { LaptopMinimal, LogOut } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { revokeOtherOwnSessions } from "@entities/auth/sessions";
import { SessionsPanel } from "@features/account-sessions/SessionsPanel";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { Button } from "@shared/ui/Button";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { Section } from "@shared/ui/glass/Section";

export function SessionsForm() {
  const { t } = useTranslation();
  const [isConfirmOpen, setIsConfirmOpen] = useState(false);
  const [isRevoking, setIsRevoking] = useState(false);
  const [version, setVersion] = useState(0);

  const handleRevokeOthers = async () => {
    setIsConfirmOpen(false);
    setIsRevoking(true);
    try {
      await revokeOtherOwnSessions();
      setVersion((value) => value + 1);
      toast.success(t("sessions.revokeOthersDone"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("sessions.revokeOthersError")));
    } finally {
      setIsRevoking(false);
    }
  };

  return (
    <Section
      icon={LaptopMinimal}
      title={t("sessions.title")}
      description={t("sessions.description")}
      aside={
        <Button variant="glassDanger" icon={LogOut} isLoading={isRevoking} onClick={() => setIsConfirmOpen(true)}>
          {t("sessions.revokeOthers")}
        </Button>
      }
    >
      <div className="mt-4">
        <SessionsPanel version={version} rowSize="default" />
      </div>
      {isConfirmOpen && (
        <ConfirmDialog
          title={t("sessions.revokeOthersTitle")}
          message={t("sessions.revokeOthersConfirm")}
          confirmLabel={t("sessions.revokeOthers")}
          cancelLabel={t("common.cancel")}
          danger
          onConfirm={() => void handleRevokeOthers()}
          onCancel={() => setIsConfirmOpen(false)}
        />
      )}
    </Section>
  );
}
