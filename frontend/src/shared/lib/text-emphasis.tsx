import type { ReactNode } from "react";

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/** Wraps each occurrence of `terms` in `text` in an inline-code chip, kept on one line, sunken like a field. */
export function withEmphasis(text: string, terms: string | string[]): ReactNode {
  const termList = Array.isArray(terms) ? terms : [terms];
  const pattern = new RegExp(`(${termList.map(escapeRegExp).join("|")})`, "g");
  return text
    .split(pattern)
    .map((part, index) =>
      termList.includes(part) ? (
        <code
          key={index}
          className="glass-well whitespace-nowrap rounded-md px-1.5 py-0.5 font-mono text-[0.9em] text-foreground"
        >
          {part}
        </code>
      ) : (
        part
      ),
    );
}

/** Turns the first occurrence of `term` in `text` into a link to `href`. */
export function withLink(text: string, term: string, href: string): ReactNode {
  const parts = text.split(term);
  if (parts.length !== 2) return text;
  return (
    <>
      {parts[0]}
      <a href={href} target="_blank" rel="noreferrer" className="text-primary hover:underline">
        {term}
      </a>
      {parts[1]}
    </>
  );
}
