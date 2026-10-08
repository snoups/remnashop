import { FileUp, Image } from "lucide-react";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { deleteBroadcastMedia, uploadBroadcastMedia } from "@entities/broadcasts/api";
import type { Broadcast } from "@entities/broadcasts/api";
import { getErrorMessage } from "@shared/api/http";
import { formatBytes } from "@shared/lib/format";
import { toast } from "@shared/lib/toast";
import { Button } from "@shared/ui/Button";

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
      <div className="flex flex-wrap items-center gap-3 rounded-2xl border border-dashed border-border p-3">
        {input}
        <FileUp className="size-5 text-muted-foreground" />
        <span className="min-w-0 flex-1 text-[12.5px] text-muted-foreground">
          {t(broadcast ? "broadcasts.editor.media.hint" : "broadcasts.editor.media.saveFirst")}
        </span>
        <Button
          variant="secondary"
          size="sm"
          disabled={!broadcast || !canSet || isBusy}
          onClick={() => inputRef.current?.click()}
        >
          {t("broadcasts.editor.media.upload")}
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-3 rounded-2xl border border-border bg-white/[0.02] p-2.5">
      {input}
      <span className="flex h-14 w-[88px] items-center justify-center rounded-xl bg-white/[0.06] text-muted-foreground">
        <Image className="size-5" />
      </span>
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span className="truncate text-[13px] font-semibold text-foreground">
          {fileName ?? t(`broadcasts.media.${broadcast.media_type}`)}
        </span>
        <span className="text-[12px] text-muted-foreground">
          {[
            t(`broadcasts.media.${broadcast.media_type}`),
            broadcast.media_size_bytes !== null ? formatBytes(broadcast.media_size_bytes, i18n.language) : null,
            t("broadcasts.editor.media.captionLimit"),
          ]
            .filter(Boolean)
            .join(" · ")}
        </span>
      </div>
      <Button
        variant="secondary"
        size="sm"
        disabled={!canSet || isBusy}
        onClick={() => inputRef.current?.click()}
      >
        {t("broadcasts.editor.media.replace")}
      </Button>
      <Button
        variant="danger"
        size="sm"
        disabled={!canDelete || isBusy}
        onClick={() => void run(() => deleteBroadcastMedia(broadcast.id), null)}
      >
        {t("common.delete")}
      </Button>
    </div>
  );
}
