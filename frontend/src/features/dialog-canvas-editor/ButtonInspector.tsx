import { ArrowRight, Eye, Link2, Palette } from "lucide-react";
import { useRef } from "react";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";

import {
  iconIdTextKey,
  isLinkButton,
  iconTextKey,
  splitTextKey,
  updateDialogText,
  urlProblem,
  urlSchemesFor,
  variableOptions,
} from "@entities/dialogs/api";
import type { DialogButtonItem, DialogCatalog } from "@entities/dialogs/api";
import type { TranslationEntry } from "@entities/translations/api";
import { TextEditorPanel } from "@features/dialog-canvas-editor/TextEditorPanel";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { EmojiPicker, type PickedEmoji } from "@entities/emoji-packs/EmojiPicker";
import { SelectDropdown } from "@shared/ui/SelectDropdown";
import { Switch } from "@shared/ui/Switch";
import { EDITOR_FIELD_CLASSNAME } from "@features/dialog-canvas-editor/field-classname";
import { EmojiThumbnail } from "@features/dialog-canvas-editor/EmojiThumbnail";
import { VariablePicker } from "@features/dialog-canvas-editor/VariablePicker";
import { Button } from "@shared/ui/Button";

function describeUrlError(
  button: DialogButtonItem,
  variableKeys: string[],
  t: TFunction,
): string | null {
  if (!isLinkButton(button.link_type)) return null;
  if (!button.url_value) return t("dialogs.inspector.buttonUrlEmpty");
  const schemes = urlSchemesFor(button.link_type);
  const problem = urlProblem(button.url_value, variableKeys, schemes);
  if (problem === null) return null;
  if (problem.kind === "scheme") {
    return t("dialogs.inspector.buttonUrlScheme", { schemes: schemes.join(", ") });
  }
  if (problem.kind === "malformed") return t("dialogs.inspector.buttonUrlMalformed");
  return t("dialogs.inspector.buttonUrlVariable", { name: problem.name });
}

interface ButtonInspectorProps {
  button: DialogButtonItem;
  windowKind: "seed" | "custom";
  catalog: DialogCatalog;
  entries: TranslationEntry[];
  activeLocale: string;
  canEditText: boolean;
  canResetText: boolean;
  canEditButtons: boolean;
  onEntrySaved: (entry: TranslationEntry) => void;
  onChange: (updated: DialogButtonItem) => void;
  onDelete: () => void;
}

export function ButtonInspector({
  button,
  windowKind,
  catalog,
  entries,
  activeLocale,
  canEditText,
  canResetText,
  canEditButtons,
  onEntrySaved,
  onChange,
  onDelete,
}: ButtonInspectorProps) {
  const { t } = useTranslation();
  const linkTypeOptions: DialogButtonItem["link_type"][] =
    windowKind === "custom"
      ? ["navigate", "url", "web_app"]
      : ["action", "navigate", "url", "web_app"];
  const { messageId } = splitTextKey(button.text_key);
  const isTextSeeded = entries.some((e) => e.message_id === messageId);
  const urlError = describeUrlError(button, catalog.variable_keys, t);

  const valueOf = (key: string): string => {
    const { messageId: id, attributeId: attr } = splitTextKey(key);
    return (
      entries.find((e) => e.locale === activeLocale && e.message_id === id && e.attribute_id === attr)
        ?.value ?? ""
    );
  };
  // Only one of the two is ever filled: a glyph rides in the label text, a
  // premium id goes to Telegram's icon field.
  const iconGlyph = valueOf(iconTextKey(button.text_key));
  const urlFieldRef = useRef<HTMLInputElement>(null);
  const iconId = valueOf(iconIdTextKey(button.text_key));

  const writeIcon = async (key: string, value: string) => {
    const { messageId: id, attributeId: attr } = splitTextKey(key);
    const updated = await updateDialogText(activeLocale, id, attr, value);
    onEntrySaved({
      locale: updated.locale,
      message_id: updated.message_id,
      attribute_id: attr,
      value: updated.value,
      default_value: updated.default_value,
    });
  };

  const handleIconPick = async (picked: PickedEmoji) => {
    try {
      if ("glyph" in picked) {
        await writeIcon(iconTextKey(button.text_key), picked.glyph);
        if (iconId) await writeIcon(iconIdTextKey(button.text_key), "");
      } else {
        await writeIcon(iconIdTextKey(button.text_key), picked.customEmojiId);
        await writeIcon(iconTextKey(button.text_key), picked.fallback);
      }
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    }
  };

  const insertIntoUrl = (token: string) => {
    const current = button.url_value ?? "";
    const at = urlFieldRef.current?.selectionStart ?? current.length;
    onChange({ ...button, url_value: `${current.slice(0, at)}${token}${current.slice(at)}` });
  };

  return (
    <div className="flex w-full flex-col gap-4">
      <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-4">
        <div className="mb-4 min-w-0">
          <span className="block truncate text-sm font-semibold text-foreground">
            {t("dialogs.inspector.buttonTitle")}
          </span>
          <span className="block truncate font-mono text-[12px] text-muted-foreground">
            {button.text_key}
          </span>
        </div>

        <div className="mb-3 flex items-center justify-between gap-3">
          <span className="text-[13px] font-medium text-foreground/80">
            {t("dialogs.inspector.enabledLabel")}
          </span>
          <Switch
            checked={!button.is_hidden}
            onChange={(value) => onChange({ ...button, is_hidden: !value })}
            disabled={!canEditButtons || button.is_system}
          />
        </div>

        <div className="mb-3">
          <span className="mb-1 block text-[13px] font-medium text-foreground/80">{t("dialogs.inspector.buttonLabel")}</span>
          <TextEditorPanel
            textKey={button.text_key}
            entries={entries}
            activeLocale={activeLocale}
            variables={variableOptions(catalog, catalog.text_variable_keys)}
            canUpdate={isTextSeeded && canEditText}
            canReset={canResetText}
            onSaved={onEntrySaved}
            required
            fieldAction={
              <EmojiPicker
                current={
                  iconId ? (
                    <EmojiThumbnail glyph={iconGlyph} customEmojiId={iconId} />
                  ) : (
                    iconGlyph || null
                  )
                }
                disabled={!canEditText}
                onPick={(picked) => void handleIconPick(picked)}
                onClear={() => void handleIconPick({ glyph: "" })}
              />
            }
          />
          {!isTextSeeded && (
            <p className="mt-1 text-[12px] text-muted-foreground">
              {t("dialogs.inspector.buttonLabelPending")}
            </p>
          )}
        </div>

        <div className="mb-3">
          <span className="mb-1 block text-[13px] font-medium text-foreground/80">{t("dialogs.inspector.buttonStyle")}</span>
          <SelectDropdown
            size="compact"
            icon={Palette}
            value={button.style ?? ""}
            disabled={!canEditButtons}
            placeholder={t("dialogs.inspector.buttonStyleNone")}
            options={[
              { value: "", label: t("dialogs.inspector.buttonStyleNone") },
              { value: "primary", label: "primary" },
              { value: "success", label: "success" },
              { value: "danger", label: "danger" },
            ]}
            onChange={(value) =>
              onChange({ ...button, style: value === "" ? null : (value as DialogButtonItem["style"]) })
            }
          />
        </div>

        <div className="mb-3">
          <span className="mb-1 block text-[13px] font-medium text-foreground/80">{t("dialogs.inspector.buttonCondition")}</span>
          <SelectDropdown
            size="compact"
            icon={Eye}
            value={button.visibility_condition ?? ""}
            disabled={!canEditButtons}
            placeholder={t("dialogs.inspector.buttonConditionNone")}
            options={[
              { value: "", label: t("dialogs.inspector.buttonConditionNone") },
              ...catalog.condition_keys.map((key) => ({ value: key, label: key })),
            ]}
            onChange={(value) => onChange({ ...button, visibility_condition: value || null })}
          />
        </div>

        <div className="mb-3">
          <span className="mb-1 block text-[13px] font-medium text-foreground/80">{t("dialogs.inspector.buttonLinkType")}</span>
          <SelectDropdown
            size="compact"
            icon={Link2}
            value={button.link_type}
            disabled={!canEditButtons || button.link_type === "action"}
            placeholder={button.link_type}
            options={linkTypeOptions.map((type) => ({ value: type, label: type }))}
            onChange={(value) => onChange({ ...button, link_type: value as DialogButtonItem["link_type"] })}
          />
        </div>

        {button.link_type === "action" && (
          <p className="mb-3 text-[12px] text-muted-foreground">
            {t("dialogs.inspector.buttonActionHint", { key: button.action_key ?? "" })}
          </p>
        )}

        {button.link_type === "navigate" && (
          <div className="mb-3">
            <span className="mb-1 block text-[13px] font-medium text-foreground/80">{t("dialogs.inspector.buttonTarget")}</span>
            <SelectDropdown
              size="compact"
              icon={ArrowRight}
              value={button.target_window_key ?? ""}
              disabled={!canEditButtons}
              placeholder={t("dialogs.inspector.buttonTargetNone")}
              options={catalog.navigable_window_keys.map((key) => ({ value: key, label: key }))}
              onChange={(value) => onChange({ ...button, target_window_key: value || null })}
            />
          </div>
        )}

        {isLinkButton(button.link_type) && (
          <div className="mb-3">
            <span className="mb-1 block text-[13px] font-medium text-foreground/80">{t("dialogs.inspector.buttonUrl")}</span>
            <div className="relative mb-1.5">
              <input
                ref={urlFieldRef}
                type="text"
                value={button.url_value ?? ""}
                disabled={!canEditButtons}
                onChange={(event) => onChange({ ...button, url_value: event.target.value })}
                className={`${EDITOR_FIELD_CLASSNAME} pr-10 ${
                  urlError === null ? "border-glass-border" : "border-error/60"
                }`}
              />
              <div className="absolute right-2 top-1/2 -translate-y-1/2">
                <VariablePicker
                  variables={variableOptions(catalog, catalog.variable_keys)}
                  format={(name) => `\${${name}}`}
                  onPick={insertIntoUrl}
                  disabled={!canEditButtons}
                />
              </div>
            </div>
            {urlError !== null && <p className="mb-1.5 text-[12px] text-error">{urlError}</p>}
          </div>
        )}

      </div>
      {canEditButtons && (
        <Button
          variant="danger"
          type="button"
          onClick={onDelete}
        >
          {t("dialogs.inspector.buttonDelete")}
        </Button>
      )}
    </div>
  );
}
