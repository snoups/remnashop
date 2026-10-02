import { Compass } from "lucide-react";
import { motion } from "motion/react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { useBrandName } from "@entities/appearance/use-appearance";
import { bounceTap } from "@shared/lib/bounceState";
import { useDocumentTitle } from "@shared/lib/use-document-title";
import { FULL_SCREEN_ACTION_CLASS, FullScreenMessage } from "@widgets/full-screen-message/FullScreenMessage";

const MotionLink = motion.create(Link);

export function NotFoundPage() {
  const { t } = useTranslation();
  const brandName = useBrandName();
  useDocumentTitle(brandName, t("errors.notFoundTitle"));

  return (
    <FullScreenMessage
      icon={Compass}
      iconClassName="text-primary"
      code="404"
      title={t("errors.notFoundTitle")}
      description={t("errors.notFoundDescription")}
      action={
        <MotionLink to="/" {...bounceTap()} className={FULL_SCREEN_ACTION_CLASS}>
          {t("errors.notFoundButton")}
        </MotionLink>
      }
    />
  );
}
