import { Link, Menu, Plus, Ticket, X } from "lucide-react";
import type { ComponentType } from "react";
import { useTranslation } from "react-i18next";

import type { BroadcastButtonKind } from "@entities/broadcasts/api";
import type { Promocode } from "@entities/promocodes/api";
import { ActionMenu } from "@shared/ui/ActionMenu";
import { Card } from "@shared/ui/Card";
import { EYEBROW_CLASS } from "@shared/ui/classes";
import { IconButton } from "@shared/ui/IconButton";
import { SelectDropdown } from "@shared/ui/SelectDropdown";
import { TextInput } from "@shared/ui/TextInput";

import { addButton, removeButton, setButtonLabel, setButtonUrl } from "@pages/broadcasts/editor/form";
import type { EditorForm } from "@pages/broadcasts/editor/form";

const MAX_BUTTONS = 10;
// phone: kind | label, then target | remove
const ROW_GRID_CLASSNAME =
  "grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)] items-center gap-2 sm:grid-cols-[110px_minmax(0,1fr)_minmax(0,1.3fr)_32px]";

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
  describePromocode: (promo: Promocode) => string;
  disabled: boolean;
}

export function ButtonsEditor({
  form,
  onChange,
  activeLocale,
  promocodes,
  describePromocode,
  disabled,
}: ButtonsEditorProps) {
  const { t } = useTranslation();
  const labels = form.contents[activeLocale]?.button_labels ?? [];
  const promocode = promocodes.find((p) => p.id === form.promocode_id);

  const target = (index: number) => {
    const button = form.buttons[index];
    if (button.kind === "URL") {
      return (
        <TextInput
          type="text"
          value={button.url ?? ""}
          disabled={disabled}
          placeholder="https://"
          onChange={(event) => onChange(setButtonUrl(form, index, event.target.value))}
          className="w-full"
        />
      );
    }
    return (
      <span className="truncate px-3 text-[12.5px] text-muted-foreground">
        {button.kind === "PROMOCODE"
          ? t("broadcasts.editor.buttons.promocodeTarget", { code: promocode?.code ?? "…" })
          : t("broadcasts.editor.buttons.menuTarget")}
      </span>
    );
  };

  return (
    <Card className="flex flex-col gap-2.5">
      <div className="flex flex-wrap items-center gap-2">
        <span className={EYEBROW_CLASS}>{t("broadcasts.editor.buttons.title")}</span>
        <span className="text-[12px] text-muted-foreground">{t("broadcasts.editor.buttons.hint")}</span>
        {!disabled && (
          <div className="ml-auto">
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
          </div>
        )}
      </div>

      {form.buttons.map((button, index) => {
        const Icon = KIND_ICON[button.kind];
        return (
          <div key={index} className={ROW_GRID_CLASSNAME}>
            <span className="flex items-center gap-1.5 text-[12.5px] text-foreground/80">
              <Icon className="size-3.5 text-muted-foreground" />
              {t(`broadcasts.editor.buttons.kind.${button.kind}`)}
            </span>
            <TextInput
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
        );
      })}

      <div className="mt-1 grid grid-cols-[110px_minmax(0,1fr)] items-center gap-2">
        <span className="text-[12.5px] text-muted-foreground">{t("broadcasts.editor.promocode.label")}</span>
        <SelectDropdown
          value={form.promocode_id === null ? "" : String(form.promocode_id)}
          variant="form"
          icon={Ticket}
          disabled={disabled}
          placeholder={t("broadcasts.editor.promocode.none")}
          options={[
            { value: "", label: t("broadcasts.editor.promocode.none") },
            ...promocodes.map((p) => ({ value: String(p.id), label: `${p.code} · ${describePromocode(p)}` })),
          ]}
          onChange={(value) => onChange({ ...form, promocode_id: value ? Number(value) : null })}
        />
      </div>
    </Card>
  );
}
