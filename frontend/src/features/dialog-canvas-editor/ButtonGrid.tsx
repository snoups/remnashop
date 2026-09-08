import { DndContext, PointerSensor, useDroppable, useSensor, useSensors, type DragEndEvent } from "@dnd-kit/core";
import { SortableContext, arrayMove, useSortable, horizontalListSortingStrategy } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";

import type { DialogButtonItem } from "@entities/dialogs/api";
import type { Selection } from "@features/dialog-canvas-editor/DialogCanvasEditor";

interface ButtonGridProps {
  buttons: DialogButtonItem[];
  textByKey: Record<string, string>;
  selection: Selection;
  onSelect: (selection: Selection) => void;
  conditionToggles: Record<string, boolean>;
  emptyLabel: string;
  canEdit: boolean;
  onReorder: (next: DialogButtonItem[]) => void;
}

export function buttonRows(buttons: DialogButtonItem[]): DialogButtonItem[][] {
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

const STYLE_BORDER_CLASSNAME: Record<string, string> = {
  primary: "border-primary/50",
  success: "border-emerald-500/60",
  danger: "border-red-500/60",
};

function buttonId(button: DialogButtonItem): string {
  return `${button.row}-${button.column}`;
}

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
  const { attributes, listeners, setNodeRef, transform, transition } = useSortable({
    id: buttonId(button),
    disabled: !draggable,
  });
  const label = textByKey[button.text_key] ?? button.text_key;
  const borderClassName = button.style ? STYLE_BORDER_CLASSNAME[button.style] : "border-white/[0.12]";

  return (
    <button
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      type="button"
      onClick={onClick}
      {...attributes}
      {...listeners}
      className={`flex flex-1 items-center justify-center gap-1.5 rounded-lg border px-3 py-2 text-center text-[13px] ${borderClassName} ${
        isEffectivelyHidden ? "opacity-40" : ""
      } ${isSelected ? "ring-2 ring-primary" : ""}`}
    >
      {button.icon_custom_emoji_id ? <span className="text-[11px] opacity-70">★</span> : null}
      <span className="truncate">{label}</span>
      {button.visibility_condition ? (
        <span className="text-[9.5px] text-muted-foreground">({button.visibility_condition})</span>
      ) : null}
    </button>
  );
}

function Row({
  id,
  buttons,
  textByKey,
  selection,
  onSelect,
  conditionToggles,
  canEdit,
  isPlaceholder,
  placeholderLabel,
}: {
  id: string;
  buttons: DialogButtonItem[];
  textByKey: Record<string, string>;
  selection: Selection;
  onSelect: (selection: Selection) => void;
  conditionToggles: Record<string, boolean>;
  canEdit: boolean;
  isPlaceholder: boolean;
  placeholderLabel?: string;
}) {
  const { setNodeRef, isOver } = useDroppable({ id });

  return (
    <div
      ref={setNodeRef}
      className={`flex min-h-10 gap-1.5 rounded-lg ${isOver ? "bg-primary/10" : ""} ${
        isPlaceholder ? "items-center justify-center border border-dashed border-white/[0.12] py-2" : ""
      }`}
    >
      {isPlaceholder && buttons.length === 0 ? (
        <span className="text-[11px] text-muted-foreground">{placeholderLabel}</span>
      ) : (
        <SortableContext items={buttons.map(buttonId)} strategy={horizontalListSortingStrategy}>
          {buttons.map((button) => (
            <CanvasButton
              key={buttonId(button)}
              button={button}
              textByKey={textByKey}
              draggable={canEdit}
              isSelected={selection.kind === "button" && selection.textKey === button.text_key}
              isEffectivelyHidden={
                button.is_hidden ||
                (button.visibility_condition
                  ? (conditionToggles[button.visibility_condition] ?? true) === false
                  : false)
              }
              onClick={() => onSelect({ kind: "button", textKey: button.text_key })}
            />
          ))}
        </SortableContext>
      )}
    </div>
  );
}

export function ButtonGrid({
  buttons,
  textByKey,
  selection,
  onSelect,
  conditionToggles,
  emptyLabel,
  canEdit,
  onReorder,
}: ButtonGridProps) {
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 8 } }));
  const containers = toContainers(buttons);
  const rowKeys = Object.keys(containers)
    .filter((key) => key !== "row-new")
    .sort((a, b) => Number(a.split("-")[1]) - Number(b.split("-")[1]));

  const handleDragEnd = (event: DragEndEvent) => {
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
      <div className="flex flex-col gap-1.5 px-3 pb-3">
        <p className="text-[12px] text-muted-foreground">{emptyLabel}</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-1.5 px-3 pb-3">
      <DndContext sensors={sensors} onDragEnd={handleDragEnd}>
        {rowKeys.map((key) => (
          <Row
            key={key}
            id={key}
            buttons={containers[key]}
            textByKey={textByKey}
            selection={selection}
            onSelect={onSelect}
            conditionToggles={conditionToggles}
            canEdit={canEdit}
            isPlaceholder={false}
          />
        ))}
        {canEdit && (
          <Row
            id="row-new"
            buttons={[]}
            textByKey={textByKey}
            selection={selection}
            onSelect={onSelect}
            conditionToggles={conditionToggles}
            canEdit={canEdit}
            isPlaceholder
          />
        )}
      </DndContext>
    </div>
  );
}
