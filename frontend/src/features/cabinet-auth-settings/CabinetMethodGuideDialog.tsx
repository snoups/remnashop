import { useTranslation } from "react-i18next";

import { GuideCopy, GuideDialog, GuideHeading } from "@shared/ui/glass/GuideDialog";

export type GuideMethod =
  | "telegramMiniApp"
  | "telegramDeeplink"
  | "telegramOAuth"
  | "google"
  | "yandex"
  | "email"
  | "captcha";

interface GuideSection {
  title: string;
  body: string;
  link?: string;
  values?: { label: string; value: string }[];
}

export function CabinetMethodGuideDialog({ method }: { method: GuideMethod }) {
  const { t } = useTranslation();
  const sections = t(`settings.cabinetAuth.guides.${method}.sections`, {
    returnObjects: true,
  }) as GuideSection[];

  return (
    <GuideDialog title={t(`settings.cabinetAuth.guides.${method}.title`)}>
      {sections.map((section) => (
        <div key={section.title}>
          <GuideHeading>{section.title}</GuideHeading>
          <p className="mt-2">{section.body}</p>
          {section.link && (
            <a
              href={section.link}
              target="_blank"
              rel="noreferrer"
              className="mt-1 inline-block text-primary hover:underline"
            >
              {section.link.replace(/^https:\/\//, "")}
            </a>
          )}
          {section.values && (
            <div className="mt-3 flex flex-col gap-2">
              {section.values.map((item) => (
                <GuideCopy key={item.label} label={item.label} value={item.value} />
              ))}
            </div>
          )}
        </div>
      ))}
    </GuideDialog>
  );
}
