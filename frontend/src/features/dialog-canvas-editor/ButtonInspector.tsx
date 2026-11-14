import { ArrowRight, Eye } from "lucide-react";
import { useRef } from "react";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";

import {
  isLinkButton,
  splitTextKey,
  updateDialogText,
  urlProblem,
  urlSchemesFor,
  variableOptions,
} from "@entities/dialogs/api";
import type { DialogButtonItem, DialogCatalog } from "@entities/dialogs/api";
import type { TranslationEntry } from "@entities/translations/api";
import { TextEditorPanel } from "@features/dialog-canvas-editor/TextEditorPanel";
import { ButtonIconPicker } from "@features/dialog-canvas-editor/ButtonIconPicker";
import { SelectDropdown } from "@shared/ui/SelectDropdown";
import { InspectorDivider, InspectorHeader, SwitchRow } from "@features/dialog-canvas-editor/InspectorParts";
import { Field } from "@shared/ui/glass/Field";
import { Input } from "@shared/ui/glass/Input";
import { SegmentedPills } from "@shared/ui/SegmentedPills";
import { VariablePicker } from "@features/dialog-canvas-editor/VariablePicker";

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

const STYLES = ["none", "primary", "success", "danger"] as const;
// an action is bound by the catalog, never picked here: an action button only changes style, place and visibility
const LINK_TYPES = ["navigate", "url", "web_app"] as const;

interface ButtonInspectorProps {
  button: DialogButtonItem;
  catalog: DialogCatalog;
  entries: TranslationEntry[];
  activeLocale: string;
  canEditText: boolean;
  canResetText: boolean;
  canEditButtons: boolean;
  onEntrySaved: (entry: TranslationEntry) => void;
  /** the window the button sits in, for the header */
  windowLabel: string;
  windowLabelOf: (key: string) => string;
  onChange: (updated: DialogButtonItem) => void;
  onBack: () => void;
}

export function ButtonInspector({
  button,
  catalog,
  entries,
  activeLocale,
  canEditText,
  canResetText,
  canEditButtons,
  onEntrySaved,
  windowLabel,
  windowLabelOf,
  onChange,
  onBack,
}: ButtonInspectorProps) {
  const { t } = useTranslation();
  const { messageId } = splitTextKey(button.text_key);
  const isTextSeeded = entries.some((e) => e.message_id === messageId);
  const urlError = describeUrlError(button, catalog.variable_keys, t);

  const urlFieldRef = useRef<HTMLInputElement>(null);

  const insertIntoUrl = (token: string) => {
    const current = button.url_value ?? "";
    const at = urlFieldRef.current?.selectionStart ?? current.length;
    onChange({ ...button, url_value: `${current.slice(0, at)}${token}${current.slice(at)}` });
  };

  return (
    <>
      <InspectorHeader title={t("dialogs.inspector.buttonTitle")} subtitle={windowLabel} onBack={onBack} />
      <InspectorDivider />

      <SwitchRow
        label={t("dialogs.inspector.enabledLabel")}
        checked={!button.is_hidden}
        onChange={(value) => onChange({ ...button, is_hidden: !value })}
        disabled={!canEditButtons || button.is_system}
      />

      <Field label={t("dialogs.inspector.buttonLabel")} required hint={isTextSeeded ? undefined : t("dialogs.inspector.buttonLabelPending")}>
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
            <ButtonIconPicker
              textKey={button.text_key}
              entries={entries}
              activeLocale={activeLocale}
              disabled={!canEditText}
              save={updateDialogText}
              onSaved={onEntrySaved}
            />
          }
        />
      </Field>

      <Field label={t("dialogs.inspector.buttonStyle")}>
        <SegmentedPills
          stretch
          compact
          disabled={!canEditButtons}
          value={button.style ?? "none"}
          onChange={(style) => onChange({ ...button, style: style === "none" ? null : style })}
          options={STYLES.map((style) => ({
            value: style,
            label: style === "none" ? t("dialogs.inspector.buttonStyleNone") : t(`dialogs.inspector.buttonStyles.${style}`),
          }))}
        />
      </Field>
      <InspectorDivider />

      <Field label={t("dialogs.inspector.buttonLinkType")}>
        {button.link_type === "action" ? (
          <span className="text-xs text-muted-foreground">
            {t("dialogs.inspector.buttonActionHint", { key: button.action_key ?? "" })}
          </span>
        ) : (
          <SegmentedPills
            stretch
            compact
            disabled={!canEditButtons}
            value={button.link_type}
            onChange={(link_type) => onChange({ ...button, link_type })}
            options={LINK_TYPES.map((type) => ({ value: type, label: t(`dialogs.inspector.linkTypes.${type}`) }))}
          />
        )}
      </Field>

      {button.link_type === "navigate" && (
        <Field label={t("dialogs.inspector.buttonTarget")}>
          <SelectDropdown
            variant="well"
            size="compact"
            icon={ArrowRight}
            value={button.target_window_key ?? ""}
            disabled={!canEditButtons}
            placeholder={t("dialogs.inspector.buttonTargetNone")}
            options={catalog.navigable_window_keys.map((key) => ({ value: key, label: windowLabelOf(key) }))}
            onChange={(value) => onChange({ ...button, target_window_key: value || null })}
          />
        </Field>
      )}

      {isLinkButton(button.link_type) && (
        <Field label={t("dialogs.inspector.buttonUrl")} required error={urlError}>
          <Input
            ref={urlFieldRef}
            mono
            value={button.url_value ?? ""}
            disabled={!canEditButtons}
            aria-invalid={urlError !== null || undefined}
            onChange={(event) => onChange({ ...button, url_value: event.target.value })}
            end={
              <span className="pr-0.5">
                <VariablePicker
                  variables={variableOptions(catalog, catalog.variable_keys)}
                  format={(name) => `\${${name}}`}
                  onPick={insertIntoUrl}
                  disabled={!canEditButtons}
                />
              </span>
            }
          />
        </Field>
      )}

      <Field label={t("dialogs.inspector.buttonCondition")}>
        <SelectDropdown
          variant="well"
          size="compact"
          icon={Eye}
          value={button.visibility_condition ?? ""}
          disabled={!canEditButtons || button.is_system}
          placeholder={t("dialogs.inspector.buttonConditionNone")}
          options={[
            { value: "", label: t("dialogs.inspector.buttonConditionNone") },
            ...catalog.condition_keys.map((key) => ({ value: key, label: key })),
          ]}
          onChange={(value) => onChange({ ...button, visibility_condition: value || null })}
        />
      </Field>
    </>
  );
}
