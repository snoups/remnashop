/** "Anna Ivanova" -> "AI", "anna" -> "AN"; "?" when there is nothing to take them from. */
export function initials(text: string | null | undefined): string {
  const words = (text ?? "").trim().split(/\s+/).filter(Boolean).map((word) => Array.from(word));
  if (words.length === 0) return "?";
  const letters = words.length > 1 ? words[0][0] + words[1][0] : words[0].slice(0, 2).join("");
  return letters.toUpperCase();
}
