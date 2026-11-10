import { FileUp, Image, Trash2 } from "lucide-react";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { deleteBroadcastMedia, uploadBroadcastMedia } from "@entities/broadcasts/api";
import type { Broadcast } from "@entities/broadcasts/api";
import { getErrorMessage } from "@shared/api/http";
import { formatBytes } from "@shared/lib/format";
import { toast } from "@shared/lib/toast";
import { Button } from "@shared/ui/Button";
import { IconButton } from "@shared/ui/IconButton";

const ACCEPT = "image/jpeg,image/png,image/webp,image/gif,video/mp4,application/pdf,application/zip";

interface MediaFieldProps {
  /** null until the broadcast is first saved: media is uploaded to an existing one */
  broadcast: Broadcast | null;
  /** the file picked in this session; the API keeps no file name */
  fileName: string | null;
  canSet: boolean;
  canDelete: boolean;
  onChanged: (broadcast: Broadcast, fileName: string | null) => void;
}

export function MediaField({ broadcast, fileName, canSet, canDelete, onChanged }: MediaFieldProps) {
  const { t, i18n } = useTranslation();
  const inputRef = useRef<HTMLInputElement>(null);
  const [isBusy, setIsBusy] = useState(false);

  const run = async (action: () => Promise<Broadcast>, name: string | null) => {
    setIsBusy(true);
    try {
      onChanged(await action(), name);
    } catch (err) {
      toast.error(getErrorMessage(err, t("broadcasts.editor.media.error")));
    } finally {
      setIsBusy(false);
    }
  };

  const input = (
    <input
      ref={inputRef}
      type="file"
      accept={ACCEPT}
      className="hidden"
      onChange={(event) => {
        const file = event.target.files?.[0];
        event.target.value = "";
        if (file && broadcast) void run(() => uploadBroadcastMedia(broadcast.id, file), file.name);
      }}
    />
  );

  if (!broadcast?.media_type) {
    return (
      <div className="flex flex-wrap items-center gap-3 rounded-[18px] border border-dashed border-white/[0.18] bg-black/[0.24] py-2 pl-3.5 pr-2">
        {input}
        <FileUp className="size-5 text-muted-foreground" />
        <span className="min-w-0 flex-1 text-xs text-muted-foreground">
          {t(broadcast ? "broadcasts.editor.media.hint" : "broadcasts.editor.media.saveFirst")}
        </span>
        <Button
          variant="glass"
          disabled={!broadcast || !canSet || isBusy}
          onClick={() => inputRef.current?.click()}
        >
          {t("broadcasts.editor.media.upload")}
        </Button>
      </div>
    );
  }

  return (
    <div className="glass-well flex flex-wrap items-center gap-3 rounded-[18px] p-2">
      {input}
      <span className="flex h-14 w-[88px] items-center justify-center rounded-[10px] bg-white/[0.06] text-muted-foreground">
        <Image className="size-5" />
      </span>
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span className="truncate text-sm font-medium text-foreground">
          {fileName ?? t(`broadcasts.media.${broadcast.media_type}`)}
        </span>
        <span className="text-xs text-muted-foreground">
          {[
            t(`broadcasts.media.${broadcast.media_type}`),
            broadcast.media_size_bytes !== null ? formatBytes(broadcast.media_size_bytes, i18n.language) : null,
          ]
            .filter(Boolean)
            .join(" · ")}{" "}
          {t("broadcasts.editor.media.captionLimit")}
        </span>
      </div>
      <Button
        variant="glass"
        disabled={!canSet || isBusy}
        onClick={() => inputRef.current?.click()}
      >
        {t("broadcasts.editor.media.replace")}
      </Button>
      <IconButton
        size="9"
        tone="glass"
        disabled={!canDelete || isBusy}
        onClick={() => void run(() => deleteBroadcastMedia(broadcast.id), null)}
      >
        {/* a glassDanger button's look, square: the bin in the error tone */}
        <Trash2 className="size-4 text-error" />
      </IconButton>
    </div>
  );
}
