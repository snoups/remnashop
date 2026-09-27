import { BotCommandsForm } from "@features/bot-commands/BotCommandsForm";
import { BotSettingsForm } from "@features/bot-settings/BotSettingsForm";
import { DialogCanvasEditor } from "@features/dialog-canvas-editor/DialogCanvasEditor";
import { EmojiPacksManager } from "@features/emoji-packs/EmojiPacksManager";
import { TranslationsEditorForm } from "@features/translations-editor/TranslationsEditorForm";

export function BotSettingsPage() {
  return (
    <div className="flex flex-col gap-4">
      <BotSettingsForm />
      <DialogCanvasEditor />
      <TranslationsEditorForm />
      <EmojiPacksManager />
      <BotCommandsForm />
    </div>
  );
}
