import { usePermissions } from "@entities/user/use-current-user";
import { BotCommandsForm } from "@features/bot-commands/BotCommandsForm";
import { BotRequirementsForm } from "@features/bot-requirements/BotRequirementsForm";
import { BotSettingsForm } from "@features/bot-settings/BotSettingsForm";
import { DialogCanvasEditor } from "@features/dialog-canvas-editor/DialogCanvasEditor";
import { EmojiPacksManager } from "@features/emoji-packs/EmojiPacksManager";
import { TranslationsEditorForm } from "@features/translations-editor/TranslationsEditorForm";

export function BotSettingsPage() {
  const permissions = usePermissions();
  return (
    <div className="flex flex-col gap-4">
      {permissions.includes("BOT_SETTINGS_VIEW") && <BotSettingsForm />}
      {permissions.includes("BOT_REQUIREMENTS_VIEW") && <BotRequirementsForm />}
      {permissions.includes("DIALOGS_CATALOG_VIEW") && permissions.includes("DIALOGS_WINDOWS_VIEW") && (
        <DialogCanvasEditor />
      )}
      {permissions.includes("TRANSLATIONS_VIEW") && <TranslationsEditorForm />}
      {permissions.includes("EMOJI_PACKS_VIEW") && <EmojiPacksManager />}
      {permissions.includes("BOT_COMMANDS_VIEW") && <BotCommandsForm />}
    </div>
  );
}
