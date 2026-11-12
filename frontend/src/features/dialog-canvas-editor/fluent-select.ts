import { sentHtmlLength } from "@entities/dialogs/api";

// `{ $x -> ... }`: only the bot knows the value, so the preview shows the default variant
const SELECT_START_RE = /\{\s*\$[A-Za-z_][A-Za-z0-9_-]*\s*->/y;
// a variant key opens a line of the select's own body: `[key]` or `*[key]`
const VARIANT_KEY_RE = /[ \t]*(\*?)\[[^\]\n]*\][ \t]*/y;
const VARIABLE_RE = /\{\s*\$[A-Za-z_][A-Za-z0-9_-]*\s*\}/g;
// `{ "[" }`: the serializer's escape for a character Fluent would read as syntax
const STRING_LITERAL_RE = /\{\s*"((?:[^"\\]|\\.)*)"\s*\}/g;

type Pick = "default" | "longest";

/** What Telegram counts of a resolved text: tags and variables left out. */
function visibleLength(text: string): number {
  return sentHtmlLength(text.replace(VARIABLE_RE, "").replace(STRING_LITERAL_RE, "$1"));
}

/** Index of the brace closing the placeable opened at `start`, -1 when unbalanced. */
function closingBrace(text: string, start: number): number {
  let depth = 0;
  for (let i = start; i < text.length; i++) {
    if (text[i] === "{") depth++;
    else if (text[i] === "}" && --depth === 0) return i;
  }
  return -1;
}

function pickVariant(body: string, pick: Pick): string {
  const variants: { isDefault: boolean; keyStart: number; valueStart: number }[] = [];
  let depth = 0;
  for (let i = 0; i < body.length; i++) {
    const char = body[i];
    if (char === "{") depth++;
    else if (char === "}") depth--;
    else if (depth === 0 && (i === 0 || body[i - 1] === "\n")) {
      VARIANT_KEY_RE.lastIndex = i;
      const match = VARIANT_KEY_RE.exec(body);
      if (match) {
        variants.push({ isDefault: match[1] === "*", keyStart: i, valueStart: i + match[0].length });
        i += match[0].length - 1;
      }
    }
  }
  // Fluent drops a variant's indent the same way
  const valueAt = (index: number) =>
    resolveSelects(
      body
        .slice(variants[index].valueStart, variants[index + 1]?.keyStart ?? body.length)
        .trim()
        .split("\n")
        .map((line) => line.trimStart())
        .join("\n"),
      pick,
    );
  if (pick === "longest") {
    return variants
      .map((_, index) => valueAt(index))
      .reduce((longest, value) => (visibleLength(value) > visibleLength(longest) ? value : longest), "");
  }
  const index = variants.findIndex((variant) => variant.isDefault);
  return index === -1 ? "" : valueAt(index);
}

/** The text with every select replaced by one of its variants, nested ones too. */
export function resolveSelects(text: string, pick: Pick = "default"): string {
  let out = "";
  let i = 0;
  while (i < text.length) {
    SELECT_START_RE.lastIndex = i;
    const match = text[i] === "{" ? SELECT_START_RE.exec(text) : null;
    if (!match) {
      out += text[i];
      i++;
      continue;
    }
    const end = closingBrace(text, i);
    if (end === -1) return out + text.slice(i);
    out += pickVariant(text.slice(i + match[0].length, end), pick);
    i = end + 1;
  }
  return out;
}

/** Mirrors modules/dialogs/validation.py's window_text_length: the longest message the
 * template can produce, each select at its longest variant, variables and tags not counted. */
export function windowTextLength(value: string): number {
  return visibleLength(resolveSelects(value, "longest"));
}
