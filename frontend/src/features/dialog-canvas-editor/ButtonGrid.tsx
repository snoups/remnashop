import {
  DndContext,
  DragOverlay,
  PointerSensor,
  closestCenter,
  defaultDropAnimationSideEffects,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
  type DropAnimation,
} from "@dnd-kit/core";
import { SortableContext, arrayMove, useSortable, horizontalListSortingStrategy } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { buttonKey, iconIdTextKey, iconTextKey } from "@entities/dialogs/api";
import { EmojiThumbnail } from "@features/dialog-canvas-editor/EmojiText";
import type { DialogButtonItem } from "@entities/dialogs/api";
import type { Selection } from "@features/dialog-canvas-editor/DialogCanvasEditor";

interface ButtonGridProps {
  buttons: DialogButtonItem[];
  textByKey: Record<string, string>;
  selection: Selection | null;
  onSelect: (selection: Selection) => void;
  emptyLabel: string;
  canEdit: boolean;
  onReorder: (next: DialogButtonItem[]) => void;
}

function buttonRows(buttons: DialogButtonItem[]): DialogButtonItem[][] {
  const byRow = new Map<number, DialogButtonItem[]>();
  for (const button of buttons) {
    const row = byRow.get(button.row) ?? [];
    row.push(button);
    byRow.set(button.row, row);
  }
  return [...byRow.entries()]
    .sort(([a], [b]) => a - b)
    .map(([, row]) => row.sort((a, b) => a.column - b.column));
}

const DROP_ANIMATION: DropAnimation = {
  sideEffects: defaultDropAnimationSideEffects({ styles: { active: { opacity: "0.3" } } }),
};

const STYLE_CLASSNAME: Record<string, string> = {
  primary: "border-primary/40 bg-primary/20",
  success: "border-emerald-500/40 bg-emerald-500/20",
  danger: "border-red-500/40 bg-red-500/20",
};

const buttonId = buttonKey;

function toContainers(buttons: DialogButtonItem[]): Record<string, DialogButtonItem[]> {
  const rows = buttonRows(buttons);
  const containers: Record<string, DialogButtonItem[]> = {};
  rows.forEach((row, index) => {
    containers[`row-${index}`] = row;
  });
  containers["row-new"] = [];
  return containers;
}

function findContainer(containers: Record<string, DialogButtonItem[]>, id: string): string | undefined {
  if (id in containers) return id;
  return Object.keys(containers).find((key) => containers[key].some((b) => buttonId(b) === id));
}

function renumber(containers: Record<string, DialogButtonItem[]>): DialogButtonItem[] {
  const rowKeys = Object.keys(containers)
    .filter((key) => key !== "row-new" && containers[key].length > 0)
    .sort((a, b) => Number(a.split("-")[1]) - Number(b.split("-")[1]));
  const flat: DialogButtonItem[] = [];
  rowKeys.forEach((key, rowIndex) => {
    containers[key].forEach((button, column) => {
      flat.push({ ...button, row: rowIndex, column });
    });
  });
  containers["row-new"].forEach((button, column) => {
    flat.push({ ...button, row: rowKeys.length, column });
  });
  return flat;
}

function useButtonLabel(button: DialogButtonItem, textByKey: Record<string, string>) {
  const { t } = useTranslation();
  // An unsaved button has no translation row yet; a saved one can still have an
  // empty label, which the bot refuses to render at all.
  const text = textByKey[button.text_key] ?? "";
  const isUnlabelled = text.trim() === "";
  return {
    isUnlabelled,
    label: isUnlabelled
      ? t(button.id === null ? "dialogs.canvas.newButton" : "dialogs.canvas.unlabelledButton")
      : text,
  };
}

function ButtonFace({
  button,
  textByKey,
  className,
}: {
  button: DialogButtonItem;
  textByKey: Record<string, string>;
  className: string;
}) {
  const { label, isUnlabelled } = useButtonLabel(button, textByKey);
  const styleClassName = button.style ? STYLE_CLASSNAME[button.style] : "border-white/[0.12]";
  const icon = textByKey[iconTextKey(button.text_key)];
  // a premium icon keeps its plain glyph, drawn if the thumbnail fails
  const iconId = textByKey[iconIdTextKey(button.text_key)];

  return (
    <span
      className={`flex items-center justify-center gap-1.5 rounded-lg border px-3 py-2 text-center text-[13px] ${styleClassName} ${className}`}
    >
      {iconId ? (
        <span className="text-[13px]">
          <EmojiThumbnail glyph={icon ?? ""} customEmojiId={iconId} />
        </span>
      ) : icon ? (
        <span className="text-[13px]">{icon}</span>
      ) : null}
      <span className={`truncate ${isUnlabelled ? "italic text-muted-foreground" : ""}`}>{label}</span>
      {button.visibility_condition ? (
        <span className="text-[9.5px] text-muted-foreground">({button.visibility_condition})</span>
      ) : null}
    </span>
  );
}

function CanvasButton({
  button,
  textByKey,
  isSelected,
  isEffectivelyHidden,
  onClick,
  draggable,
}: {
  button: DialogButtonItem;
  textByKey: Record<string, string>;
  isSelected: boolean;
  isEffectivelyHidden: boolean;
  onClick: () => void;
  draggable: boolean;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: buttonId(button),
    disabled: !draggable,
  });

  return (
    <button
      ref={setNodeRef}
      style={{
        transform: CSS.Transform.toString(transform),
        transition,
        // Without this a touch drag scrolls the page instead of moving the button.
        touchAction: draggable ? "none" : undefined,
      }}
      type="button"
      onClick={() => onClick()}
      {...attributes}
      {...listeners}
      className={`flex flex-1 ${draggable ? "cursor-grab active:cursor-grabbing" : "cursor-pointer"}`}
    >
      <ButtonFace
        button={button}
        textByKey={textByKey}
        className={`w-full transition ${isEffectivelyHidden ? "opacity-40 hover:opacity-70" : ""} ${
          isDragging
            ? // The real button stays as the gap the overlay will drop back into.
              "opacity-25"
            : isSelected
              ? "ring-2 ring-primary"
              : "hover:ring-1 hover:ring-white/25"
        }`}
      />
    </button>
  );
}

function Row({
  id,
  buttons,
  textByKey,
  selection,
  onSelect,
  canEdit,
}: {
  id: string;
  buttons: DialogButtonItem[];
  textByKey: Record<string, string>;
  selection: Selection | null;
  onSelect: (selection: Selection) => void;
  canEdit: boolean;
}) {
  const { setNodeRef, isOver } = useDroppable({ id });

  return (
    <div
      ref={setNodeRef}
      className={`flex min-h-10 gap-1.5 rounded-lg transition-colors ${
        isOver ? "bg-primary/10 ring-1 ring-primary/40" : ""
      }`}
    >
      <SortableContext items={buttons.map(buttonId)} strategy={horizontalListSortingStrategy}>
        {buttons.map((button) => (
          <CanvasButton
            key={buttonId(button)}
            button={button}
            textByKey={textByKey}
            draggable={canEdit}
            isSelected={selection?.kind === "button" && selection.buttonKey === buttonId(button)}
            isEffectivelyHidden={button.is_hidden}
            onClick={() => onSelect({ kind: "button", buttonKey: buttonId(button) })}
          />
        ))}
      </SortableContext>
    </div>
  );
}

/** Where a dropped button opens a new row. Mounted only while something is
 * being dragged: a permanent dashed strip sits in the layout doing nothing the
 * rest of the time. */
function NewRowIndicator({ id }: { id: string }) {
  const { setNodeRef, isOver } = useDroppable({ id });

  return (
    <div ref={setNodeRef} className="flex h-5 items-center">
      <span
        className={`relative h-[3px] w-full rounded-full transition-colors ${
          isOver ? "bg-primary shadow-[0_0_14px_color-mix(in_srgb,var(--color-primary)_55%,transparent)]" : "bg-primary/35"
        }`}
      >
        <span className="absolute -left-0.5 -top-[2.5px] size-2 rounded-full bg-inherit" />
        <span className="absolute -right-0.5 -top-[2.5px] size-2 rounded-full bg-inherit" />
      </span>
    </div>
  );
}

export function ButtonGrid({
  buttons,
  textByKey,
  selection,
  onSelect,
  emptyLabel,
  canEdit,
  onReorder,
}: ButtonGridProps) {
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 8 } }));
  const [dragged, setDragged] = useState<{ button: DialogButtonItem; width: number } | null>(null);
  const containers = toContainers(buttons);
  const rowKeys = Object.keys(containers)
    .filter((key) => key !== "row-new")
    .sort((a, b) => Number(a.split("-")[1]) - Number(b.split("-")[1]));

  const handleDragStart = (event: DragStartEvent) => {
    const button = buttons.find((b) => buttonId(b) === String(event.active.id));
    if (!button) return;
    // The overlay is outside the row's flex layout, so it needs the width the
    // button actually had, or it collapses to its text.
    setDragged({ button, width: event.active.rect.current.initial?.width ?? 0 });
  };

  const handleDragEnd = (event: DragEndEvent) => {
    setDragged(null);
    const { active, over } = event;
    if (!over) return;
    const activeId = String(active.id);
    const overId = String(over.id);
    const fromContainer = findContainer(containers, activeId);
    const toContainer = findContainer(containers, overId) ?? overId;
    if (!fromContainer || !toContainer) return;
    if (fromContainer === toContainer && activeId === overId) return;

    if (fromContainer === toContainer) {
      const items = containers[fromContainer];
      const activeIndex = items.findIndex((b) => buttonId(b) === activeId);
      const overIndex = items.findIndex((b) => buttonId(b) === overId);
      if (activeIndex === -1 || overIndex === -1) return;
      onReorder(renumber({ ...containers, [fromContainer]: arrayMove(items, activeIndex, overIndex) }));
      return;
    }

    const from = [...containers[fromContainer]];
    const activeIndex = from.findIndex((b) => buttonId(b) === activeId);
    if (activeIndex === -1) return;
    const [moved] = from.splice(activeIndex, 1);

    const to = [...containers[toContainer]];
    const overIndex = to.findIndex((b) => buttonId(b) === overId);
    to.splice(overIndex === -1 ? to.length : overIndex, 0, moved);

    onReorder(renumber({ ...containers, [fromContainer]: from, [toContainer]: to }));
  };

  if (buttons.length === 0 && !canEdit) {
    return (
      <div className="flex flex-col gap-1.5">
        <p className="text-[12px] text-muted-foreground">{emptyLabel}</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-1.5">
      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragStart={handleDragStart}
        onDragEnd={handleDragEnd}
        onDragCancel={() => setDragged(null)}
      >
        {rowKeys.map((key) => (
          <Row
            key={key}
            id={key}
            buttons={containers[key]}
            textByKey={textByKey}
            selection={selection}
            onSelect={onSelect}
            canEdit={canEdit}
          />
        ))}
        {canEdit && dragged !== null && <NewRowIndicator id="row-new" />}
        <DragOverlay dropAnimation={DROP_ANIMATION}>
          {dragged && (
            <div style={{ width: dragged.width }} className="scale-[1.03] cursor-grabbing">
              <ButtonFace
                button={dragged.button}
                textByKey={textByKey}
                className="w-full bg-surface shadow-lg shadow-black/40 ring-2 ring-primary/60"
              />
            </div>
          )}
        </DragOverlay>
      </DndContext>
    </div>
  );
}
