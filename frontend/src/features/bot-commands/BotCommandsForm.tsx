import { MoreVertical, Terminal } from "lucide-react";
import { motion, Reorder, useDragControls } from "motion/react";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { getErrorMessage } from "@shared/api/http";
import { type BotCommandItem, getBotCommands, updateBotCommands } from "@entities/settings/api";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { Spinner } from "@shared/ui/Spinner";
import { Switch } from "@shared/ui/Switch";

type Row = BotCommandItem & { id: number };

const toBotCommandItem = ({ command, enabled }: Row): BotCommandItem => ({
  command,
  enabled,
});

interface CommandRowProps {
  row: Row;
  onChange: (field: "enabled", value: boolean) => void;
}

function CommandRow({ row, onChange }: CommandRowProps) {
  const { t } = useTranslation();
  const dragControls = useDragControls();

  return (
    <Reorder.Item
      value={row}
      as="div"
      dragListener={false}
      dragControls={dragControls}
      className="flex items-center gap-2 rounded-xl border border-border bg-input/60 p-2"
    >
      <button
        type="button"
        onPointerDown={(event) => dragControls.start(event)}
        aria-label={t("settings.botCommands.dragHandle")}
        className="flex cursor-grab items-center justify-center rounded-full p-1.5 text-foreground/60 transition-colors hover:bg-white/5 active:cursor-grabbing"
      >
        <MoreVertical className="size-4" />
      </button>
      <span className="flex-1 truncate font-mono text-sm text-foreground/80">/{row.command}</span>
      <Switch
        checked={row.enabled}
        onChange={(checked) => onChange("enabled", checked)}
        ariaLabel={t("settings.botCommands.enabledLabel")}
      />
    </Reorder.Item>
  );
}

export function BotCommandsForm() {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const [rows, setRows] = useState<Row[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const nextRowId = useRef(0);
  const toRow = (item: BotCommandItem): Row => ({ ...item, id: nextRowId.current++ });

  const [state] = useAsyncResource(getBotCommands, (items) => setRows(items.map(toRow)));

  const updateRow = (index: number, field: "enabled", value: boolean) => {
    setRows((current) =>
      current.map((row, i) => (i === index ? { ...row, [field]: value } : row)),
    );
  };

  const handleSave = async () => {
    setIsSubmitting(true);

    try {
      const result = await updateBotCommands(rows.map(toBotCommandItem));
      setRows(result.commands.map(toRow));
      if (result.telegram_sync_failed) {
        toast.warning(t("settings.botCommands.savedTelegramSyncFailed"));
      } else {
        toast.success(t("settings.botCommands.saved"));
      }
    } catch (err) {
      toast.error(getErrorMessage(err, t("auth.errors.genericError")));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-4">
      <div className="flex items-center gap-2.5">
        <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] text-foreground backdrop-blur-md">
          <Terminal className="size-4" />
        </div>
        <div>
          <h2 className="text-sm font-bold text-foreground">{t("settings.botCommands.title")}</h2>
          <p className="text-[12.5px] text-muted-foreground">{t("settings.botCommands.description")}</p>
        </div>
      </div>

      <div className="mt-4 flex flex-col gap-4">
        {state.kind === "loading" && (
          <Spinner />
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
                />
              ))}
            </Reorder.Group>

            <div className="flex gap-2">
              <motion.button
                type="button"
                onClick={() => void handleSave()}
                disabled={isSubmitting}
                {...bounceTap(bounceStrength)}
                className="w-fit rounded-full bg-accent px-4 py-2 text-sm font-medium text-primary transition-colors hover:bg-primary/20 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {isSubmitting ? t("settings.botCommands.saving") : t("settings.botCommands.save")}
              </motion.button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
