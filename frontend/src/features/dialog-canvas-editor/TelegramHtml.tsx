import type { ReactNode } from "react";

import { parseTelegramHtml, renderVariablesSample } from "@entities/broadcasts/telegram-html";
import type { TgNode } from "@entities/broadcasts/telegram-html";
import { EmojiThumbnail } from "@features/dialog-canvas-editor/EmojiThumbnail";

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
          <code key={index} className="font-mono text-sm text-sky-300">
            {children}
          </code>
        );
      case "pre":
        return (
          <pre key={index} className="my-1 whitespace-pre-wrap rounded-md bg-black/20 p-2 font-mono text-sm text-sky-300">
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

/** Telegram HTML as Telegram shows it; `{ $x }` tokens without a value stay as written. */
export function TelegramHtml({ value, values = {} }: { value: string; values?: Record<string, string> }) {
  return <>{renderNodes(parseTelegramHtml(renderVariablesSample(value, values)))}</>;
}
