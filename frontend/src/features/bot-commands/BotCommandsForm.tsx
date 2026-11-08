import { closestCenter, DndContext, type DragEndEvent, KeyboardSensor, PointerSensor, useSensor, useSensors } from "@dnd-kit/core";
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { GripVertical, Terminal } from "lucide-react";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { getErrorMessage } from "@shared/api/http";
import { type BotCommandItem, getBotCommands, updateBotCommands } from "@entities/settings/api";
import { usePermissions } from "@entities/user/use-current-user";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { ErrorState } from "@shared/ui/glass/EmptyState";
import { Spinner } from "@shared/ui/Spinner";
import { Button } from "@shared/ui/Button";
import { Section, SectionRows } from "@shared/ui/glass/Section";
import { Switch } from "@shared/ui/glass/Switch";
import { SaveFooter } from "@shared/ui/SaveFooter";

type Row = BotCommandItem & { id: number };

const toBotCommandItem = ({ command, enabled }: Row): BotCommandItem => ({
  command,
  enabled,
});

interface CommandRowProps {
  row: Row;
  onChange: (field: "enabled", value: boolean) => void;
  readOnly: boolean;
}

function CommandRow({ row, onChange, readOnly }: CommandRowProps) {
  const { attributes, listeners, setNodeRef, setActivatorNodeRef, transform, transition, isDragging } = useSortable({
    id: row.id,
    disabled: readOnly,
  });

  return (
    // a Row's geometry (60px pill, 32px ends 14px in, the switch 16px) with a drag handle for the icon
    <div
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={`flex min-h-15 items-center gap-3 rounded-full pl-3.5 pr-4 ${isDragging ? "glass-control relative z-10" : ""}`}
    >
      {readOnly ? (
        <span className="size-8 shrink-0" />
      ) : (
        <button
          ref={setActivatorNodeRef}
          type="button"
          {...attributes}
          {...listeners}
          className="flex size-8 shrink-0 cursor-grab touch-none items-center justify-center rounded-full bg-white/[0.06] text-foreground/70 transition-colors hover:bg-white/[0.1] hover:text-foreground active:cursor-grabbing"
        >
          <GripVertical className="size-4" />
        </button>
      )}
      <span className="min-w-0 flex-1 truncate font-mono text-[13px] text-foreground">/{row.command}</span>
      <Switch checked={row.enabled} onChange={(checked) => onChange("enabled", checked)} disabled={readOnly} />
    </div>
  );
}

export function BotCommandsForm() {
  const { t } = useTranslation();
  const canManage = usePermissions().includes("BOT_COMMANDS_MANAGE");
  const [rows, setRows] = useState<Row[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  // from 1: dnd-kit treats id 0 as missing
  const nextRowId = useRef(1);
  const toRow = (item: BotCommandItem): Row => ({ ...item, id: nextRowId.current++ });

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );
  const handleDragEnd = ({ active, over }: DragEndEvent) => {
    if (!over || active.id === over.id) return;
    setRows((current) =>
      arrayMove(
        current,
        current.findIndex((row) => row.id === active.id),
        current.findIndex((row) => row.id === over.id),
      ),
    );
  };

  // what the server holds, in order: Save lights up only when rows differ from it
  const [saved, setSaved] = useState<BotCommandItem[]>([]);
  const [state] = useAsyncResource(getBotCommands, {
    onSuccess: (items) => {
      setRows(items.map(toRow));
      setSaved(items);
    },
  });
  const dirty =
    rows.length !== saved.length ||
    rows.some((row, index) => row.command !== saved[index]?.command || row.enabled !== saved[index]?.enabled);

  const updateRow = (index: number, field: "enabled", value: boolean) => {
    setRows((current) =>
      current.map((row, i) => (i === index ? { ...row, [field]: value } : row)),
    );
  };

  const [isResetting, setIsResetting] = useState(false);

  // the default order and switches, as a draft: nothing changes until Save
  const handleReset = async () => {
    setIsResetting(true);
    try {
      setRows((await getBotCommands(undefined, true)).map(toRow));
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    } finally {
      setIsResetting(false);
    }
  };

  const handleSave = async () => {
    setIsSubmitting(true);

    try {
      const result = await updateBotCommands(rows.map(toBotCommandItem));
      setRows(result.commands.map(toRow));
      setSaved(result.commands);
      if (result.telegram_sync_failed) {
        toast.warning(t("settings.botCommands.savedTelegramSyncFailed"));
      } else {
        toast.success(t("common.saved"));
      }
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Section
      icon={Terminal}
      title={t("settings.botCommands.title")}
      description={t("settings.botCommands.description")}
      footer={
        state.kind === "ready" &&
        canManage && (
          <SaveFooter
            dirty={dirty}
            saving={isSubmitting}
            onSave={() => void handleSave()}
            beside={
              <Button variant="glassDanger" isLoading={isResetting} onClick={() => void handleReset()}>
                {t("settings.botCommands.reset")}
              </Button>
            }
          />
        )
      }
    >
      {state.kind === "loading" && <Spinner size="card" />}
      {state.kind === "error" && <ErrorState text={t("common.loadError")} />}
      {state.kind === "ready" && (
        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
          <SortableContext items={rows.map((row) => row.id)} strategy={verticalListSortingStrategy}>
            <SectionRows>
              {rows.map((row, index) => (
                <CommandRow
                  key={row.id}
                  row={row}
                  onChange={(field, value) => updateRow(index, field, value)}
                  readOnly={!canManage}
                />
              ))}
            </SectionRows>
          </SortableContext>
        </DndContext>
      )}
    </Section>
  );
}
