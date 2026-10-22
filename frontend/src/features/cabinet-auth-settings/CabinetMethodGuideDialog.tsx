import { useTranslation } from "react-i18next";

import { CopyableValue } from "@shared/ui/CopyableValue";
import { GuideDialog } from "@shared/ui/GuideDialog";

export type GuideMethod = "telegramBot" | "telegramOAuth" | "google" | "yandex" | "email";

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
          <h3 className="text-sm font-bold text-foreground">{section.title}</h3>
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
                <CopyableValue key={item.label} label={item.label} value={item.value} />
              ))}
            </div>
          )}
        </div>
      ))}
    </GuideDialog>
  );
}
