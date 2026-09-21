import { BotCommandsForm } from "@features/bot-commands/BotCommandsForm";
import { BotSettingsForm } from "@features/bot-settings/BotSettingsForm";
import { TranslationsEditorForm } from "@features/translations-editor/TranslationsEditorForm";

export function BotSettingsPage() {
  return (
    <div className="flex flex-col gap-4">
      <BotSettingsForm />
      <BotCommandsForm />
      <TranslationsEditorForm />
    </div>
  );
}
