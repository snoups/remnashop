import { useTranslation } from "react-i18next";

export function DashboardPage() {
  const { t } = useTranslation();

  return (
    <div className="flex flex-1 items-center justify-center">
      <div className="text-center">
        <h2 className="text-xl font-semibold text-foreground">{t("dashboard.welcomeTitle")}</h2>
        <p className="mt-2 text-muted-foreground">{t("dashboard.welcomeSubtitle")}</p>
      </div>
    </div>
  );
}
