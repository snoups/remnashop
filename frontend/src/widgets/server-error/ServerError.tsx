import { ServerCrash, Unplug, type LucideIcon } from "lucide-react";
import { motion } from "motion/react";
import { useTranslation } from "react-i18next";

import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { FULL_SCREEN_ACTION_CLASS, FullScreenMessage } from "@widgets/full-screen-message/FullScreenMessage";

interface FullScreenErrorProps {
  icon: LucideIcon;
  titleKey: string;
  descriptionKey: string;
}

function FullScreenError({ icon, titleKey, descriptionKey }: FullScreenErrorProps) {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();

  return (
    <FullScreenMessage
      icon={icon}
      iconClassName="text-error"
      title={t(titleKey)}
      description={t(descriptionKey)}
      action={
        <motion.button
          type="button"
          onClick={() => window.location.reload()}
          {...bounceTap(bounceStrength)}
          className={FULL_SCREEN_ACTION_CLASS}
        >
          {t("errors.retry")}
        </motion.button>
      }
    />
  );
}

export function ServerError() {
  return <FullScreenError icon={ServerCrash} titleKey="errors.serverErrorTitle" descriptionKey="errors.serverErrorDescription" />;
}

export function ServerUnreachable() {
  return (
    <FullScreenError icon={Unplug} titleKey="errors.serverUnreachableTitle" descriptionKey="errors.serverUnreachableDescription" />
  );
}
