import { PREMIUM_EMOJI_RE } from "@entities/dialogs/api";

export type TgNode =
  | string
  | {
      tag: "b" | "i" | "u" | "s" | "code" | "pre" | "blockquote" | "spoiler" | "a" | "emoji";
      href?: string;
      emojiId?: string;
      children: TgNode[];
    };

type TgTag = Exclude<TgNode, string>["tag"];

const TAG_BY_ELEMENT: Record<string, TgTag> = {
  b: "b",
  strong: "b",
  i: "i",
  em: "i",
  u: "u",
  ins: "u",
  s: "s",
  strike: "s",
  del: "s",
  a: "a",
  code: "code",
  pre: "pre",
  blockquote: "blockquote",
  "tg-spoiler": "spoiler",
  "tg-emoji": "emoji",
};

// elements whose text content is code, never prose
const DROPPED_ELEMENTS = new Set(["script", "style", "template"]);
const EMOJI_ID_RE = /^\d{1,24}$/;
const SAFE_HREF_RE = /^(https?:|tg:)/i;

function walk(parent: Node): TgNode[] {
  const nodes: TgNode[] = [];
  for (const child of Array.from(parent.childNodes)) {
    if (child.nodeType === Node.TEXT_NODE) {
      if (child.textContent) nodes.push(child.textContent);
      continue;
    }
    if (!(child instanceof Element)) continue;
    const name = child.localName;
    if (DROPPED_ELEMENTS.has(name)) continue;
    const tag = TAG_BY_ELEMENT[name];
    if (!tag) {
      nodes.push(...walk(child));
      continue;
    }
    const emojiId = child.getAttribute("emoji-id") ?? "";
    if (tag === "emoji" && !EMOJI_ID_RE.test(emojiId)) {
      nodes.push(...walk(child));
      continue;
    }
    const node: Exclude<TgNode, string> = { tag, children: walk(child) };
    if (tag === "a") {
      const href = child.getAttribute("href")?.trim();
      if (href && SAFE_HREF_RE.test(href)) node.href = href;
    }
    if (tag === "emoji") node.emojiId = emojiId;
    nodes.push(node);
  }
  return nodes;
}

// DOMParser builds an inert document: no script runs, no resource loads
export function parseTelegramHtml(html: string): TgNode[] {
  return walk(new DOMParser().parseFromString(html, "text/html").body);
}

function escapeHtml(value: string): string {
  return value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

const VARIABLE_RE = /\{\s*\$([A-Za-z_][A-Za-z0-9_]*)\s*\}/g;

export function renderVariablesSample(text: string, values: Record<string, string>): string {
  return text
    .replace(VARIABLE_RE, (match, name: string) => (Object.hasOwn(values, name) ? escapeHtml(values[name]) : match))
    .replace(PREMIUM_EMOJI_RE, '<tg-emoji emoji-id="$2">$1</tg-emoji>');
}
