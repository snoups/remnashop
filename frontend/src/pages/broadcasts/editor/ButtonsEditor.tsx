import { Link, Menu, MousePointerClick, Plus, Ticket, X } from "lucide-react";
import type { ComponentType } from "react";
import { useTranslation } from "react-i18next";

import type { BroadcastButtonKind } from "@entities/broadcasts/api";
import type { Promocode } from "@entities/promocodes/api";
import { ActionMenu } from "@shared/ui/ActionMenu";
import { EmptyState } from "@shared/ui/glass/EmptyState";
import { Field } from "@shared/ui/glass/Field";
import { Input } from "@shared/ui/glass/Input";
import { IconCircle } from "@shared/ui/glass/IconCircle";
import { Section, SectionRows } from "@shared/ui/glass/Section";
import { IconButton } from "@shared/ui/IconButton";
import { SelectDropdown } from "@shared/ui/SelectDropdown";

import { addButton, removeButton, setButtonLabel, setButtonUrl } from "@pages/broadcasts/editor/form";
import type { EditorForm } from "@pages/broadcasts/editor/form";

const MAX_BUTTONS = 10;
// phone: kind | label, then target | remove
const ROW_GRID_CLASSNAME =
  "grid grid-cols-[32px_minmax(0,1fr)_minmax(0,1fr)_32px] items-center gap-3 sm:grid-cols-[32px_80px_minmax(0,1fr)_minmax(0,1.3fr)_32px]";

const PROMOCODE_VARIABLE_RE = /\{\s*\$promocode\s*\}/;

const KIND_ICON: Record<BroadcastButtonKind, ComponentType<{ className?: string }>> = {
  URL: Link,
  PROMOCODE: Ticket,
  MENU: Menu,
};

const KINDS: BroadcastButtonKind[] = ["URL", "PROMOCODE", "MENU"];

interface ButtonsEditorProps {
  form: EditorForm;
  onChange: (form: EditorForm) => void;
  activeLocale: string;
  promocodes: Promocode[];
  /** "−30% · until 31.10.2026 · up to 1000 activations" */
  disabled: boolean;
}

export function ButtonsEditor({
  form,
  onChange,
  activeLocale,
  promocodes,
  disabled,
}: ButtonsEditorProps) {
  const { t } = useTranslation();
  const labels = form.contents[activeLocale]?.button_labels ?? [];

  const hasPromocodeButton = form.buttons.some((button) => button.kind === "PROMOCODE");
  // a texts-only promocode: picked here only once a text uses it, or kept while one is set
  const textsUsePromocode = [
    ...Object.values(form.contents).map((content) => content.text),
    ...Object.values(form.email_contents).flatMap((content) => [content.subject, content.html]),
  ].some((text) => PROMOCODE_VARIABLE_RE.test(text));
  const promocodeSelect = (
    <SelectDropdown
      value={form.promocode_id === null ? "" : String(form.promocode_id)}
      variant="well"
      size="compact"
      icon={Ticket}
      disabled={disabled}
      placeholder={t("broadcasts.editor.promocode.none")}
      options={[
        { value: "", label: t("broadcasts.editor.promocode.none") },
        ...promocodes.map((p) => ({ value: String(p.id), label: p.code })),
      ]}
      onChange={(value) => onChange({ ...form, promocode_id: value ? Number(value) : null })}
    />
  );

  const target = (index: number) => {
    const button = form.buttons[index];
    if (button.kind === "URL") {
      return (
        <Input
          type="text"
          value={button.url ?? ""}
          disabled={disabled}
          placeholder="https://"
          onChange={(event) => onChange(setButtonUrl(form, index, event.target.value))}
          className="w-full"
        />
      );
    }
    // the broadcast has one promocode: every promocode button, and { $promocode }, open the same
    if (button.kind === "PROMOCODE") return promocodeSelect;
    return <span className="truncate px-3.5 text-sm text-muted-foreground">{t("broadcasts.editor.buttons.menuTarget")}</span>;
  };

  return (
    <Section
      icon={MousePointerClick}
      title={t("broadcasts.editor.buttons.title")}
      description={t("broadcasts.editor.buttons.hint")}
      aside={
        !disabled && (
            <ActionMenu
              trigger={{ label: t("broadcasts.editor.buttons.add"), icon: Plus }}
              items={KINDS.map((kind) => ({
                label: t(`broadcasts.editor.buttons.kind.${kind}`),
                icon: KIND_ICON[kind],
                disabled: form.buttons.length >= MAX_BUTTONS,
                hint: t("broadcasts.editor.buttons.limit", { count: MAX_BUTTONS }),
                onClick: () => onChange(addButton(form, kind)),
              }))}
            />
        )
      }
    >
      {form.buttons.length === 0 ? (
        <div className="mt-4">
          <EmptyState icon={MousePointerClick} text={t("broadcasts.editor.buttons.empty")} />
        </div>
      ) : (
        // a list as settings rows look: a 60px pill per button; rounded, so the line between bends at its ends as a Row's does
        <SectionRows>
          {form.buttons.map((button, index) => (
            <div key={index} className={`${ROW_GRID_CLASSNAME} rounded-full px-3.5 py-3`}>
              <IconCircle icon={KIND_ICON[button.kind]} />
              {/* narrow screens: the icon names the kind */}
              <span className="hidden truncate text-sm font-medium text-foreground sm:block">
                {t(`broadcasts.editor.buttons.kind.${button.kind}`)}
              </span>
              <Input
                type="text"
                value={labels[index] ?? ""}
                disabled={disabled}
                maxLength={64}
                placeholder={t("broadcasts.editor.buttons.label")}
                onChange={(event) => onChange(setButtonLabel(form, activeLocale, index, event.target.value))}
                className="w-full"
              />
              {target(index)}
              <IconButton size="8" tone="danger" disabled={disabled} onClick={() => onChange(removeButton(form, index))}>
                <X className="size-4" />
              </IconButton>
            </div>
          ))}
        </SectionRows>
      )}

      {/* no promocode button: the broadcast's promocode still feeds { $promocode } in the texts */}
      {!hasPromocodeButton && (textsUsePromocode || form.promocode_id !== null) && (
        <div className="mt-4">
          <Field label={t("broadcasts.editor.promocode.label")}>{promocodeSelect}</Field>
        </div>
      )}
    </Section>
  );
}
