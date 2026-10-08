import { Image } from "lucide-react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import type { BroadcastMediaType } from "@entities/broadcasts/api";
import { parseTelegramHtml, renderVariablesSample } from "@entities/broadcasts/telegram-html";
import type { TgNode } from "@entities/broadcasts/telegram-html";
import { EmojiThumbnail } from "@features/dialog-canvas-editor/EmojiText";
import { Card } from "@shared/ui/Card";
import { EYEBROW_CLASS } from "@shared/ui/classes";

import type { EditorForm } from "@pages/broadcasts/editor/form";

const SAMPLE_DAYS_LEFT = 4;
const DAY_MS = 24 * 3600 * 1000;

function renderNodes(nodes: TgNode[]): ReactNode[] {
  return nodes.map((node, index) => {
    if (typeof node === "string") return node;
    const children = renderNodes(node.children);
    switch (node.tag) {
      case "b":
        return <b key={index}>{children}</b>;
      case "i":
        return <i key={index}>{children}</i>;
      case "u":
        return <u key={index}>{children}</u>;
      case "s":
        return <s key={index}>{children}</s>;
      case "code":
        return (
          <code key={index} className="font-mono text-[12.5px] text-sky-300">
            {children}
          </code>
        );
      case "pre":
        return (
          <pre key={index} className="my-1 whitespace-pre-wrap rounded-md bg-black/20 p-2 font-mono text-[12.5px] text-sky-300">
            {children}
          </pre>
        );
      case "blockquote":
        return (
          <blockquote key={index} className="my-1 border-l-2 border-sky-400 pl-2">
            {children}
          </blockquote>
        );
      case "spoiler":
        return (
          <span key={index} className="rounded bg-white/25 text-transparent">
            {children}
          </span>
        );
      case "a":
        return node.href ? (
          <a key={index} href={node.href} target="_blank" rel="noreferrer" className="text-sky-400 hover:underline">
            {children}
          </a>
        ) : (
          <span key={index}>{children}</span>
        );
      case "emoji": {
        const glyph = node.children.filter((c) => typeof c === "string").join("");
        return node.emojiId ? (
          <EmojiThumbnail key={index} glyph={glyph} customEmojiId={node.emojiId} />
        ) : (
          <span key={index}>{children}</span>
        );
      }
      default:
        return null;
    }
  });
}

interface TelegramPreviewProps {
  form: EditorForm;
  locale: string;
  mediaType: BroadcastMediaType | null;
  mediaName: string | null;
  promocodeCode: string | null;
}

export function TelegramPreview({ form, locale, mediaType, mediaName, promocodeCode }: TelegramPreviewProps) {
  const { t, i18n } = useTranslation();
  const content = form.contents[locale] ?? form.contents[form.default_locale];
  const name = t("broadcasts.editor.preview.sampleName");
  const values: Record<string, string> = {
    name,
    username: "@anna",
    plan: "Pro",
    expire_date: new Date(Date.now() + SAMPLE_DAYS_LEFT * DAY_MS).toLocaleDateString(i18n.language),
    days_left: String(SAMPLE_DAYS_LEFT),
    bonus_days: "3",
    points: "120",
    promocode: promocodeCode ?? t("common.none"),
  };
  const nodes = parseTelegramHtml(renderVariablesSample(content?.text ?? "", values));
  const labels = content?.button_labels ?? [];
  const buttons = [
    ...form.buttons.map((_, index) => labels[index] || t("broadcasts.editor.buttons.label")),
    ...(form.category === "MARKETING" ? [t("broadcasts.editor.preview.unsubscribe")] : []),
  ];

  return (
    <Card className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <span className={EYEBROW_CLASS}>{t("broadcasts.editor.preview.title")}</span>
        <span className="ml-auto text-[12px] text-muted-foreground">
          {t("broadcasts.editor.preview.as", { name, locale: locale.toUpperCase() })}
        </span>
      </div>
      <div className="flex flex-col gap-1 rounded-2xl bg-[#0e1621] p-3.5">
        <div className="max-w-[300px] overflow-hidden rounded-[14px_14px_14px_4px] bg-[#182533]">
          {mediaType && (
            <div className="flex h-[150px] flex-col items-center justify-center gap-1.5 bg-white/[0.05] text-[12px] text-[#6f7aa3]">
              <Image className="size-5" />
              {[t(`broadcasts.media.${mediaType}`), mediaName].filter(Boolean).join(" · ")}
            </div>
          )}
          <div className="whitespace-pre-wrap break-words px-2.5 pb-1.5 pt-2 text-[13.5px] leading-[1.45] text-[#e8ecfb]">
            {nodes.length > 0 ? renderNodes(nodes) : <span className="text-[#6f7aa3]">{t("broadcasts.editor.preview.empty")}</span>}
          </div>
          <div className="px-2.5 pb-1.5 text-right text-[11px] text-[#6f7aa3]">
            {new Date().toLocaleTimeString(i18n.language, { hour: "2-digit", minute: "2-digit" })}
          </div>
        </div>
        {buttons.length > 0 && (
          <div className="flex max-w-[300px] flex-col gap-[3px]">
            {buttons.map((label, index) => (
              <span
                key={index}
                className="flex h-[34px] items-center justify-center truncate rounded-lg bg-[#182533]/85 px-2 text-[13px] text-[#e8ecfb]"
              >
                {label}
              </span>
            ))}
          </div>
        )}
      </div>
    </Card>
  );
}
