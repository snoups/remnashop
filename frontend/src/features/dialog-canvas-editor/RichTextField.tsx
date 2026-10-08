import { forwardRef, useEffect, useImperativeHandle, useRef } from "react";

import { PREMIUM_EMOJI_RE, splitPremiumEmoji } from "@entities/dialogs/api";
import { emojiThumbnailUrl } from "@entities/emoji-packs/api";

// Copy inside the field keeps premium emoji; text/plain carries only glyphs.
const MARKUP_MIME = "application/x-remnashop-markup";
const EMOJI_CLASSNAME = "inline-block size-[1.25em] align-[-0.25em] object-contain";

export interface RichTextFieldHandle {
  /** Inserts markup at the last caret position the field had. */
  insert: (markup: string) => void;
  /** Wraps the selection in `open`/`close`; with none, inserts the pair and leaves the caret between. */
  wrap: (open: string, close: string) => void;
}

interface RichTextFieldProps {
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  className?: string;
}

function escapeHtml(text: string): string {
  return text
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

/** Premium emoji markup becomes an atomic <img>, so the caret, selection and
 * Backspace treat it as one character. */
function markupToHtml(markup: string): string {
  return splitPremiumEmoji(markup)
    .map((part) =>
      typeof part === "string"
        ? escapeHtml(part)
        : `<img src="${emojiThumbnailUrl(part.customEmojiId)}" alt="${escapeHtml(part.glyph)}" data-emoji-id="${part.customEmojiId}" data-glyph="${escapeHtml(part.glyph)}" draggable="false" class="${EMOJI_CLASSNAME}">`,
    )
    .join("");
}

function glyphImageUrl(glyph: string): string {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><text x="16" y="26" font-size="26" text-anchor="middle">${escapeHtml(glyph)}</text></svg>`;
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}

function serializeNode(node: Node): string {
  // Chrome writes a run of spaces as nbsp while editing; Telegram wants plain ones
  if (node.nodeType === Node.TEXT_NODE) return (node.textContent ?? "").replaceAll("\u00a0", " ");
  if (!(node instanceof HTMLElement)) return "";
  if (node.dataset.emojiId) return `[${node.dataset.glyph ?? ""}](emoji:${node.dataset.emojiId})`;
  if (node.tagName === "BR") return "\n";
  return serializeChildren(node);
}

/** Back to markup. Browsers still wrap lines in <div>/<p> on some paths
 * (Firefox, spellcheck fixes), so a block starts a new line. */
function serializeChildren(parent: ParentNode): string {
  const nodes = Array.from(parent.childNodes);
  // the browser's placeholder <br> that keeps a trailing empty line visible
  if (parent instanceof HTMLElement && parent.isContentEditable && nodes.at(-1)?.nodeName === "BR") {
    nodes.pop();
  }
  let out = "";
  for (const node of nodes) {
    const isBlock = node.nodeName === "DIV" || node.nodeName === "P";
    out += (isBlock && out !== "" && !out.endsWith("\n") ? "\n" : "") + serializeNode(node);
  }
  return out;
}

function insertMarkup(markup: string) {
  // execCommand goes through the browser's own editing, so undo keeps working
  if (markup.match(PREMIUM_EMOJI_RE)) document.execCommand("insertHTML", false, markupToHtml(markup));
  else document.execCommand("insertText", false, markup);
}

/** A multi-line field that shows premium emoji as images instead of their
 * `[glyph](emoji:id)` markup, while `value` stays that markup. */
export const RichTextField = forwardRef<RichTextFieldHandle, RichTextFieldProps>(function RichTextField(
  { value, onChange, disabled = false, className = "" },
  ref,
) {
  const rootRef = useRef<HTMLDivElement>(null);
  // what the DOM already shows; an echo of our own onChange must not rebuild it
  const renderedRef = useRef<string | null>(null);
  const savedRangeRef = useRef<Range | null>(null);

  useEffect(() => {
    const root = rootRef.current;
    if (!root || value === renderedRef.current) return;
    root.innerHTML = markupToHtml(value);
    renderedRef.current = value;
  }, [value]);

  // The picker and variable chips take focus away; remember where the caret was.
  useEffect(() => {
    const handleSelectionChange = () => {
      const selection = document.getSelection();
      if (selection?.rangeCount && rootRef.current?.contains(selection.anchorNode)) {
        savedRangeRef.current = selection.getRangeAt(0).cloneRange();
      }
    };
    document.addEventListener("selectionchange", handleSelectionChange);
    return () => document.removeEventListener("selectionchange", handleSelectionChange);
  }, []);

  // A pack imported before thumbnails were stored has none: draw the glyph
  // instead. Same <img> node, so a caret sitting next to it stays put.
  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;
    const handleError = (event: Event) => {
      const img = event.target;
      if (!(img instanceof HTMLImageElement) || !img.dataset.emojiId || img.src.startsWith("data:")) return;
      img.src = glyphImageUrl(img.dataset.glyph ?? "");
    };
    root.addEventListener("error", handleError, true);
    return () => root.removeEventListener("error", handleError, true);
  }, []);

  // focus moves the caret to the start; put it back where the field last had it
  const restoreCaret = (root: HTMLDivElement): Selection | null => {
    root.focus();
    const selection = document.getSelection();
    const saved = savedRangeRef.current;
    if (selection) {
      selection.removeAllRanges();
      if (saved && root.contains(saved.startContainer)) {
        selection.addRange(saved);
      } else {
        const end = document.createRange();
        end.selectNodeContents(root);
        end.collapse(false);
        selection.addRange(end);
      }
    }
    return selection;
  };

  useImperativeHandle(ref, () => ({
    insert(markup: string) {
      const root = rootRef.current;
      if (!root) return;
      restoreCaret(root);
      insertMarkup(markup);
    },
    wrap(open: string, close: string) {
      const root = rootRef.current;
      if (!root) return;
      const selection = restoreCaret(root);
      const range = selection?.rangeCount ? selection.getRangeAt(0) : null;
      const inner = range && !range.collapsed ? serializeChildren(range.cloneContents()) : "";
      insertMarkup(`${open}${inner}${close}`);
      if (inner) return;
      for (let i = 0; i < close.length; i++) selection?.modify("move", "backward", "character");
    },
  }));

  const emit = () => {
    const root = rootRef.current;
    if (!root) return;
    const next = serializeChildren(root);
    renderedRef.current = next;
    onChange(next);
  };

  const copySelection = (event: React.ClipboardEvent) => {
    const selection = document.getSelection();
    if (!selection?.rangeCount || selection.isCollapsed) return false;
    const markup = serializeChildren(selection.getRangeAt(0).cloneContents());
    event.clipboardData.setData(MARKUP_MIME, markup);
    event.clipboardData.setData("text/plain", markup.replace(PREMIUM_EMOJI_RE, "$1"));
    event.preventDefault();
    return true;
  };

  return (
    <div
      ref={rootRef}
      contentEditable={!disabled}
      suppressContentEditableWarning
      spellCheck={false}
      onInput={emit}
      onKeyDown={(event) => {
        if (event.key !== "Enter") return;
        // a bare Enter would open a <div> block; a <br> is exactly one "\n"
        event.preventDefault();
        document.execCommand("insertLineBreak");
      }}
      onPaste={(event) => {
        event.preventDefault();
        insertMarkup(event.clipboardData.getData(MARKUP_MIME) || event.clipboardData.getData("text/plain"));
      }}
      onCopy={copySelection}
      onCut={(event) => {
        if (copySelection(event)) document.execCommand("delete");
      }}
      className={`whitespace-pre-wrap break-words ${disabled ? "opacity-50" : ""} ${className}`}
    />
  );
});
