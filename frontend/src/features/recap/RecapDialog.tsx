import { Copy, Download, EyeOff, Sparkles } from "lucide-react";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { getRecap } from "@entities/overview/api";
import { RecapCard } from "@features/recap/RecapCard";
import type { RecapBlock, RecapField } from "@features/recap/RecapCard";
import { getSystemMetadata } from "@shared/api/system";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { Button } from "@shared/ui/Button";
import { ChoiceChip } from "@shared/ui/ChoiceChip";
import { DialogCard } from "@shared/ui/glass/DialogCard";
import { DialogHeader } from "@shared/ui/glass/DialogHeader";
import { ErrorState } from "@shared/ui/glass/EmptyState";
import { Input } from "@shared/ui/glass/Input";
import { Switch } from "@shared/ui/glass/Switch";
import { Modal } from "@shared/ui/Modal";
import { Spinner } from "@shared/ui/Spinner";

const BLOCKS: RecapBlock[] = ["totals", "month", "infra"];
const HIDEABLE: RecapField[] = ["revenueTotal", "monthRevenue", "customers", "payers"];
const NOTE_MAX_LENGTH = 40;
// sharp on a retina screen and in a chat preview
const PIXEL_RATIO = 2;

function toggle<T>(list: T[], value: T): T[] {
  return list.includes(value) ? list.filter((item) => item !== value) : [...list, value];
}

async function snapshot(node: HTMLElement): Promise<Blob> {
  // loaded on the first copy or download: nothing else in the dashboard needs it
  const { toBlob } = await import("html-to-image");
  const blob = await toBlob(node, {
    pixelRatio: PIXEL_RATIO,
    cacheBust: true,
    // whole pixels: a fractional height leaves the last row of the canvas empty, white in a viewer
    width: Math.floor(node.getBoundingClientRect().width),
    height: Math.floor(node.getBoundingClientRect().height),
    // whatever the card doesn't cover is its own colour, not transparent
    backgroundColor: getComputedStyle(node).backgroundColor,
    // square corners in the image: a chat or a post rounds it its own way
    style: { borderRadius: "0" },
  });
  if (!blob) throw new Error("empty snapshot");
  return blob;
}

function fileName(): string {
  return `recap-${new Date().toISOString().slice(0, 10)}.png`;
}

export function RecapDialog({ onClose }: { onClose: () => void }) {
  return (
    <Modal onClose={onClose} size="xl">
      <RecapBody />
    </Modal>
  );
}

function RecapBody() {
  const { t } = useTranslation();
  const [state] = useAsyncResource(getRecap);
  const [metadataState] = useAsyncResource(getSystemMetadata);
  const [blocks, setBlocks] = useState<RecapBlock[]>(BLOCKS);
  const [hidden, setHidden] = useState<RecapField[]>([]);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState<"copy" | "download" | null>(null);
  const cardRef = useRef<HTMLDivElement>(null);

  const run = async (action: "copy" | "download") => {
    const node = cardRef.current;
    if (!node) return;
    setBusy(action);
    try {
      const blob = await snapshot(node);
      if (action === "copy") {
        await navigator.clipboard.write([new ClipboardItem({ [blob.type]: blob })]);
        toast.success(t("recap.copied"));
      } else {
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = fileName();
        link.click();
        URL.revokeObjectURL(url);
      }
    } catch {
      toast.error(t(action === "copy" ? "recap.copyError" : "recap.downloadError"));
    } finally {
      setBusy(null);
    }
  };

  const ready = state.kind === "ready";
  return (
    <>
      <DialogHeader icon={Sparkles} title={t("recap.title")} />
      {/* plates in the body: 12px in, 12px corners nested in the dialog's 24px */}
      <div className="min-h-0 flex-1 overflow-y-auto p-3 [--dialog-pad:0.75rem]">
        {state.kind === "loading" && <Spinner size="card" />}
        {state.kind === "error" && <ErrorState text={t("common.loadError")} />}
        {state.kind === "ready" && (
          <div className="flex flex-wrap items-start gap-3">
            {/* fills what the card leaves, so the body keeps its 12px and no more */}
            <div className="flex min-w-64 flex-1 flex-col gap-3">
              <DialogCard variant="form" title={t("recap.controls.blocks")}>
                {BLOCKS.map((block) => (
                  <div key={block} className="flex items-center justify-between gap-3 text-[13px] font-medium text-foreground">
                    {t(`recap.blocks.${block}`)}
                    <Switch
                      checked={blocks.includes(block)}
                      // the panel didn't answer: no numbers to show in this block
                      disabled={block === "infra" && state.data.nodes === null}
                      onChange={() => setBlocks((prev) => toggle(prev, block))}
                    />
                  </div>
                ))}
              </DialogCard>
              <DialogCard variant="form" title={t("recap.controls.hide")}>
                <div className="flex flex-wrap gap-1.5">
                  {HIDEABLE.map((field) => (
                    <ChoiceChip
                      glass
                      size="sm"
                      key={field}
                      active={hidden.includes(field)}
                      onClick={() => setHidden((prev) => toggle(prev, field))}
                    >
                      {hidden.includes(field) && <EyeOff className="size-3.5" />}
                      {t(`recap.fields.${field}`)}
                    </ChoiceChip>
                  ))}
                </div>
              </DialogCard>
              <DialogCard variant="form" title={t("recap.controls.note")}>
                <Input
                  value={note}
                  maxLength={NOTE_MAX_LENGTH}
                  placeholder={t("recap.controls.notePlaceholder")}
                  onChange={(event) => setNote(event.target.value)}
                />
              </DialogCard>
            </div>
            <RecapCard
              ref={cardRef}
              recap={state.data}
              version={metadataState.kind === "ready" ? metadataState.data.version : null}
              blocks={blocks}
              hidden={hidden}
              note={note}
            />
          </div>
        )}
      </div>
      <div className="flex shrink-0 justify-end gap-2 border-t border-white/[0.08] p-4">
        <Button variant="glass" type="button" disabled={!ready || busy !== null} icon={Copy} isLoading={busy === "copy"} onClick={() => void run("copy")}>
          {t("recap.controls.copy")}
        </Button>
        <Button
          variant="glassAccent"
          type="button"
          disabled={!ready || busy !== null}
          icon={Download}
          isLoading={busy === "download"}
          onClick={() => void run("download")}
        >
          {t("recap.controls.download")}
        </Button>
      </div>
    </>
  );
}
