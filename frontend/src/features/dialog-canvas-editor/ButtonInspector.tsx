import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";

import {
  URL_SCHEMES,
  iconIdTextKey,
  iconTextKey,
  splitTextKey,
  updateDialogText,
  urlProblem,
} from "@entities/dialogs/api";
import type { DialogButtonItem, DialogCatalog } from "@entities/dialogs/api";
import type { TranslationEntry } from "@entities/translations/api";
import { TextEditorPanel } from "@features/dialog-canvas-editor/TextEditorPanel";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { EmojiPicker, type PickedEmoji } from "@shared/ui/EmojiPicker";

function describeUrlError(
  button: DialogButtonItem,
  variableKeys: string[],
  t: TFunction,
): string | null {
  if (button.link_type !== "url") return null;
  if (!button.url_value) return t("dialogs.inspector.buttonUrlEmpty");
  const problem = urlProblem(button.url_value, variableKeys);
  if (problem === null) return null;
  return problem.kind === "scheme"
    ? t("dialogs.inspector.buttonUrlScheme", { schemes: URL_SCHEMES.join(", ") })
    : t("dialogs.inspector.buttonUrlVariable", { name: problem.name });
}

interface ButtonInspectorProps {
  button: DialogButtonItem;
  windowKind: "seed" | "custom";
  catalog: DialogCatalog;
  entries: TranslationEntry[];
  locales: string[];
  activeLocale: string;
  onActiveLocaleChange: (locale: string) => void;
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
  locales,
  activeLocale,
  onActiveLocaleChange,
  canEditText,
  canResetText,
  canEditButtons,
  onEntrySaved,
  onChange,
  onDelete,
}: ButtonInspectorProps) {
  const { t } = useTranslation();
  const linkTypeOptions: DialogButtonItem["link_type"][] =
    windowKind === "custom" ? ["navigate", "url"] : ["action", "navigate", "url"];
  const { messageId, attributeId } = splitTextKey(button.text_key);
  const isTextSeeded = entries.some((e) => e.message_id === messageId);
  const isLabelEmpty =
    (
      entries.find(
        (e) => e.locale === activeLocale && e.message_id === messageId && e.attribute_id === attributeId,
      )?.value ?? ""
    ).trim() === "";
  const urlError = describeUrlError(button, catalog.variable_keys, t);

  const valueOf = (key: string): string => {
    const { messageId: id, attributeId: attr } = splitTextKey(key);
    return (
      entries.find((e) => e.locale === activeLocale && e.message_id === id && e.attribute_id === attr)
        ?.value ?? ""
    );
  };
  // Only one of the two is ever filled: a glyph rides in the label text, a
  // premium id goes to Telegram's own icon field.
  const iconGlyph = valueOf(iconTextKey(button.text_key));
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
      toast.error(getErrorMessage(err, t("auth.errors.genericError")));
    }
  };

  return (
    <div className="flex w-full flex-col gap-4">
      <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-4">
        <h3 className="mb-3 text-[13px] font-semibold text-foreground">{t("dialogs.inspector.buttonTitle")}</h3>

        <label className="mb-3 block">
          <span className="mb-1 block text-[12px] text-muted-foreground">{t("dialogs.inspector.buttonLabel")}</span>
          <TextEditorPanel
            textKey={button.text_key}
            entries={entries}
            locales={locales}
            activeLocale={activeLocale}
            onActiveLocaleChange={onActiveLocaleChange}
            variableKeys={catalog.text_variable_keys}
            canUpdate={isTextSeeded && canEditText}
            canReset={canResetText}
            onSaved={onEntrySaved}
            fieldAction={
              <EmojiPicker
                current={iconGlyph || null}
                disabled={!canEditText}
                onPick={(picked) => void handleIconPick(picked)}
                onClear={() => void handleIconPick({ glyph: "" })}
              />
            }
          />
          {!isTextSeeded && (
            <p className="mt-1 text-[11.5px] text-muted-foreground">
              {t("dialogs.inspector.buttonLabelPending")}
            </p>
          )}
          {isTextSeeded && isLabelEmpty && (
            <p className="mt-1 text-[11.5px] text-error">{t("dialogs.inspector.buttonLabelEmpty")}</p>
          )}
        </label>

        <label className="mb-3 block">
          <span className="mb-1 block text-[12px] text-muted-foreground">{t("dialogs.inspector.buttonStyle")}</span>
          <select
            className="w-full rounded-lg border border-white/[0.12] bg-white/[0.04] px-2.5 py-1.5 text-[13px] text-foreground disabled:opacity-50"
            value={button.style ?? ""}
            disabled={!canEditButtons}
            onChange={(event) =>
              onChange({ ...button, style: event.target.value === "" ? null : (event.target.value as DialogButtonItem["style"]) })
            }
          >
            <option value="">{t("dialogs.inspector.buttonStyleNone")}</option>
            <option value="primary">primary</option>
            <option value="success">success</option>
            <option value="danger">danger</option>
          </select>
        </label>

        <label className="mb-3 block">
          <span className="mb-1 block text-[12px] text-muted-foreground">{t("dialogs.inspector.buttonCondition")}</span>
          <select
            className="w-full rounded-lg border border-white/[0.12] bg-white/[0.04] px-2.5 py-1.5 text-[13px] text-foreground disabled:opacity-50"
            value={button.visibility_condition ?? ""}
            disabled={!canEditButtons}
            onChange={(event) => onChange({ ...button, visibility_condition: event.target.value || null })}
          >
            <option value="">{t("dialogs.inspector.buttonConditionNone")}</option>
            {catalog.condition_keys.map((key) => (
              <option key={key} value={key}>
                {key}
              </option>
            ))}
          </select>
        </label>

        <label className="mb-3 block">
          <span className="mb-1 block text-[12px] text-muted-foreground">{t("dialogs.inspector.buttonLinkType")}</span>
          <select
            className="w-full rounded-lg border border-white/[0.12] bg-white/[0.04] px-2.5 py-1.5 text-[13px] text-foreground disabled:opacity-50"
            value={button.link_type}
            disabled={!canEditButtons || button.link_type === "action"}
            onChange={(event) => onChange({ ...button, link_type: event.target.value as DialogButtonItem["link_type"] })}
          >
            {linkTypeOptions.map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </select>
        </label>

        {button.link_type === "action" && (
          <p className="mb-3 text-[11.5px] text-muted-foreground">
            {t("dialogs.inspector.buttonActionHint", { key: button.action_key ?? "" })}
          </p>
        )}

        {button.link_type === "navigate" && (
          <label className="mb-3 block">
            <span className="mb-1 block text-[12px] text-muted-foreground">{t("dialogs.inspector.buttonTarget")}</span>
            <select
              className="w-full rounded-lg border border-white/[0.12] bg-white/[0.04] px-2.5 py-1.5 text-[13px] text-foreground disabled:opacity-50"
              value={button.target_window_key ?? ""}
              disabled={!canEditButtons}
              onChange={(event) => onChange({ ...button, target_window_key: event.target.value || null })}
            >
              <option value="" disabled>
                {t("dialogs.inspector.buttonTargetNone")}
              </option>
              {catalog.navigable_window_keys.map((key) => (
                <option key={key} value={key}>
                  {key}
                </option>
              ))}
            </select>
          </label>
        )}

        {button.link_type === "url" && (
          <label className="mb-3 block">
            <span className="mb-1 block text-[12px] text-muted-foreground">{t("dialogs.inspector.buttonUrl")}</span>
            <input
              type="text"
              value={button.url_value ?? ""}
              disabled={!canEditButtons}
              onChange={(event) => onChange({ ...button, url_value: event.target.value })}
              className={`mb-1.5 w-full rounded-lg border bg-white/[0.04] px-2.5 py-1.5 text-[13px] text-foreground disabled:opacity-50 ${
                urlError === null ? "border-white/[0.12]" : "border-error/60"
              }`}
            />
            {urlError !== null && <p className="mb-1.5 text-[11.5px] text-error">{urlError}</p>}
            <div className="flex flex-wrap gap-1">
              {catalog.variable_keys.map((name) => (
                <button
                  key={name}
                  type="button"
                  disabled={!canEditButtons}
                  onClick={() => onChange({ ...button, url_value: `${button.url_value ?? ""}\${${name}}` })}
                  className="rounded-full border border-white/[0.12] px-2 py-0.5 text-[11px] text-foreground/70 hover:bg-white/[0.06] disabled:opacity-30"
                >
                  {`\${${name}}`}
                </button>
              ))}
            </div>
          </label>
        )}

        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={button.is_hidden}
            disabled={!canEditButtons}
            onChange={(event) => onChange({ ...button, is_hidden: event.target.checked })}
          />
          <span className="text-[13px] text-foreground">{t("dialogs.inspector.buttonHidden")}</span>
        </label>
      </div>
      {canEditButtons && (
        <button
          type="button"
          onClick={onDelete}
          className="rounded-full border border-white/[0.12] px-3 py-2 text-[12.5px] text-error hover:bg-white/[0.06]"
        >
          {t("dialogs.inspector.buttonDelete")}
        </button>
      )}
    </div>
  );
}
