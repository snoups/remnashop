import { Monitor } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { readStorage, writeStorage } from "@shared/lib/safe-storage";
import { Button } from "@shared/ui/Button";
import { DialogHeader } from "@shared/ui/DialogHeader";
import { Modal } from "@shared/ui/Modal";
import { useModalClose } from "@shared/ui/modal-hooks";

const DISMISSED_KEY = "dashboard-mobile-notice-dismissed";
const MOBILE_QUERY = "(width < 768px)";

export function MobileNotice() {
  const [dismissed, setDismissed] = useState(() => readStorage(DISMISSED_KEY, "session") === "1");
  const [isMobile, setIsMobile] = useState(() => window.matchMedia(MOBILE_QUERY).matches);

  useEffect(() => {
    const query = window.matchMedia(MOBILE_QUERY);
    const update = () => setIsMobile(query.matches);
    update();
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);

  if (dismissed || !isMobile) return null;

  return (
    <Modal onClose={() => {
      writeStorage(DISMISSED_KEY, "1", "session");
      setDismissed(true);
    }}>
      <MobileNoticeBody />
    </Modal>
  );
}

function MobileNoticeBody() {
  const { t } = useTranslation();
  const close = useModalClose();

  return (
    <div role="dialog" aria-modal="true" aria-label={t("mobileNotice.title")} aria-describedby="mobile-notice-description">
      <DialogHeader icon={Monitor} title={t("mobileNotice.title")} />
      <div className="flex flex-col gap-5 p-5">
        <p id="mobile-notice-description" className="text-sm leading-relaxed text-foreground/80">
          {t("mobileNotice.description")}
        </p>
        <Button variant="solid" className="w-full" onClick={close}>
          {t("mobileNotice.continueButton")}
        </Button>
      </div>
    </div>
  );
}
