import type { ParseKeys } from "i18next";
import { ServerCrash, Unplug, type LucideIcon } from "lucide-react";
import { useTranslation } from "react-i18next";

import { FULL_SCREEN_ACTION_CLASS, FullScreenMessage } from "@widgets/full-screen-message/FullScreenMessage";
import { Pressable } from "@shared/ui/Pressable";

interface FullScreenErrorProps {
  icon: LucideIcon;
  titleKey: ParseKeys;
  descriptionKey: ParseKeys;
}

function FullScreenError({ icon, titleKey, descriptionKey }: FullScreenErrorProps) {
  const { t } = useTranslation();

  return (
    <FullScreenMessage
      icon={icon}
      iconClassName="text-error"
      title={t(titleKey)}
      description={t(descriptionKey)}
      action={
        <Pressable
          type="button"
          onClick={() => window.location.reload()}
          className={`${FULL_SCREEN_ACTION_CLASS}`}
        >
          {t("errors.retry")}
        </Pressable>
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
