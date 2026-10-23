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
import { ErrorState } from "@shared/ui/EmptyState";
import { Spinner } from "@shared/ui/Spinner";
import { Switch } from "@shared/ui/Switch";
import { Button } from "@shared/ui/Button";
import { Card } from "@shared/ui/Card";
import { CardHeader } from "@shared/ui/CardHeader";

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
    <div
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={`flex items-center gap-2 rounded-full border border-border bg-input/60 py-2 pl-2 pr-2.5 ${isDragging ? "relative z-10" : ""}`}
    >
      {!readOnly && (
        <button
          ref={setActivatorNodeRef}
          type="button"
          {...attributes}
          {...listeners}
          className="flex cursor-grab touch-none items-center justify-center rounded-full p-1.5 text-foreground/60 transition-colors hover:bg-white/[0.06] active:cursor-grabbing"
        >
          <GripVertical className="size-4" />
        </button>
      )}
      <span className="flex-1 truncate font-mono text-sm text-foreground/80">/{row.command}</span>
      <Switch
        checked={row.enabled}
        onChange={(checked) => onChange("enabled", checked)}
        disabled={readOnly}
      />
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

  const [state] = useAsyncResource(getBotCommands, { onSuccess: (items) => setRows(items.map(toRow)) });

  const updateRow = (index: number, field: "enabled", value: boolean) => {
    setRows((current) =>
      current.map((row, i) => (i === index ? { ...row, [field]: value } : row)),
    );
  };

  const [isResettingOrder, setIsResettingOrder] = useState(false);

  const handleResetOrder = async () => {
    setIsResettingOrder(true);
    try {
      const defaults = await getBotCommands(undefined, true);
      const rank = new Map(defaults.map((item, index) => [item.command, index]));
      // only the order resets, unsaved toggles stay
      setRows((current) =>
        [...current].sort((a, b) => (rank.get(a.command) ?? 0) - (rank.get(b.command) ?? 0)),
      );
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    } finally {
      setIsResettingOrder(false);
    }
  };

  const handleSave = async () => {
    setIsSubmitting(true);

    try {
      const result = await updateBotCommands(rows.map(toBotCommandItem));
      setRows(result.commands.map(toRow));
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
    <Card>
      <CardHeader
        icon={Terminal}
        title={t("settings.botCommands.title")}
        description={t("settings.botCommands.description")}
      />

      <div className="mt-4 flex flex-col gap-4">
        {state.kind === "loading" && (
          <Spinner size="card" />
        )}
        {state.kind === "error" && (
          <ErrorState text={t("common.loadError")} />
        )}
        {state.kind === "ready" && (
          <>
            <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
              <SortableContext items={rows.map((row) => row.id)} strategy={verticalListSortingStrategy}>
                <div className="flex flex-col gap-2">
                  {rows.map((row, index) => (
                    <CommandRow
                      key={row.id}
                      row={row}
                      onChange={(field, value) => updateRow(index, field, value)}
                      readOnly={!canManage}
                    />
                  ))}
                </div>
              </SortableContext>
            </DndContext>

            {canManage && (
            <div className="flex gap-2">
              <Button
                variant="accent"
                className="w-fit"
                type="button"
                onClick={() => void handleSave()}
                disabled={isSubmitting}
              >
                {isSubmitting ? t("common.saving") : t("common.save")}
              </Button>
              <Button
                variant="outline"
                className="w-fit"
                isLoading={isResettingOrder}
                onClick={() => void handleResetOrder()}
              >
                {t("settings.botCommands.resetOrder")}
              </Button>
            </div>
            )}
          </>
        )}
      </div>
    </Card>
  );
}
