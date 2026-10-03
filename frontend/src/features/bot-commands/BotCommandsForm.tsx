import { Loader2, MoreVertical, Terminal } from "lucide-react";
import { motion, Reorder, useDragControls } from "motion/react";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { getErrorMessage } from "@shared/api/http";
import { type BotCommandItem, getBotCommands, updateBotCommands } from "@entities/settings/api";
import { usePermissions } from "@entities/user/use-current-user";
import { bounceTap } from "@shared/lib/bounceState";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
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
  const dragControls = useDragControls();

  return (
    <Reorder.Item
      value={row}
      as="div"
      dragListener={false}
      dragControls={dragControls}
      className="flex items-center gap-2 rounded-full border border-border bg-input/60 py-2 pl-2 pr-2.5"
    >
      {!readOnly && (
        <button
          type="button"
          onPointerDown={(event) => dragControls.start(event)}
          className="flex cursor-grab items-center justify-center rounded-full p-1.5 text-foreground/60 transition-colors hover:bg-white/5 active:cursor-grabbing"
        >
          <MoreVertical className="size-4" />
        </button>
      )}
      <span className="flex-1 truncate font-mono text-sm text-foreground/80">/{row.command}</span>
      <Switch
        checked={row.enabled}
        onChange={(checked) => onChange("enabled", checked)}
        disabled={readOnly}
      />
    </Reorder.Item>
  );
}

export function BotCommandsForm() {
  const { t } = useTranslation();
  const canManage = usePermissions().includes("BOT_COMMANDS_MANAGE");
  const [rows, setRows] = useState<Row[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const nextRowId = useRef(0);
  const toRow = (item: BotCommandItem): Row => ({ ...item, id: nextRowId.current++ });

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
      // Only the order resets -- unsaved toggles stay as the admin left them.
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
          <p className="text-sm text-error">{t("settings.botCommands.loadError")}</p>
        )}
        {state.kind === "ready" && (
          <>
            <Reorder.Group as="div" axis="y" values={rows} onReorder={setRows} className="flex flex-col gap-2">
              {rows.map((row, index) => (
                <CommandRow
                  key={row.id}
                  row={row}
                  onChange={(field, value) => updateRow(index, field, value)}
                  readOnly={!canManage}
                />
              ))}
            </Reorder.Group>

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
              <motion.button
                type="button"
                onClick={() => void handleResetOrder()}
                disabled={isResettingOrder}
                {...bounceTap()}
                className="flex w-fit h-9 items-center gap-1.5 rounded-full border border-white/[0.12] px-4 text-sm font-medium text-foreground/80 transition-colors hover:bg-white/[0.06] disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isResettingOrder && <Loader2 className="size-3.5 animate-spin" />}
                {t("settings.botCommands.resetOrder")}
              </motion.button>
            </div>
            )}
          </>
        )}
      </div>
    </Card>
  );
}
