import { AppearanceSettingsForm } from "@features/appearance-settings/AppearanceSettingsForm";

export function AppearanceSettingsPage() {
  return (
    <div className="flex flex-col gap-4">
      <AppearanceSettingsForm target="dashboard" />
      <AppearanceSettingsForm target="cabinet" />
    </div>
  );
}
