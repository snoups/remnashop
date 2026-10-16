import { useCallback, useEffect, useRef, useState } from "react";

import { fetchEmailImage } from "@entities/broadcasts/api";

const STORED_SRC_RE = /src="bc-image:(\d+)"/g;
/** the link schemes the backend accepts in a letter */
export const EMAIL_URL_RE = /^(https?:\/\/|mailto:)\S+$/;
// what the backend accepts on each tag; every other tag keeps no attributes
const ALLOWED_ATTRS: Record<string, string[]> = { A: ["href", "data-button"], IMG: ["alt"] };

/** stored `bc-image:<id>` sources → displayable URLs, the id kept as `data-image-id` */
export function toEditorHtml(html: string, urls: Record<number, string>): string {
  return html.replace(STORED_SRC_RE, (_, id: string) => `src="${urls[Number(id)] ?? ""}" data-image-id="${id}"`);
}

/** the editor's HTML reduced to what the backend's email allowlist accepts */
export function toStoredHtml(html: string): string {
  // a <template> parses inertly: no image loads, no handlers run
  const template = document.createElement("template");
  template.innerHTML = html;
  for (const el of [...template.content.querySelectorAll("*")]) {
    const imageId = el.getAttribute("data-image-id");
    if (el.tagName === "IMG" && !/^\d+$/.test(imageId ?? "")) {
      el.remove();
      continue;
    }
    if (el.tagName === "A" && !EMAIL_URL_RE.test(el.getAttribute("href") ?? "")) {
      el.replaceWith(...el.childNodes);
      continue;
    }
    const keep = ALLOWED_ATTRS[el.tagName] ?? [];
    for (const name of el.getAttributeNames()) {
      if (!keep.includes(name)) el.removeAttribute(name);
    }
    if (el.tagName === "IMG") el.setAttribute("src", `bc-image:${imageId}`);
  }
  return template.innerHTML;
}

/** pasted HTML without the images whose `data-image-id` isn't one of the broadcast's own */
export function dropForeignImages(html: string, urls: Record<number, string>): string {
  const template = document.createElement("template");
  template.innerHTML = html;
  for (const img of template.content.querySelectorAll("img[data-image-id]")) {
    if (!((Number(img.getAttribute("data-image-id"))) in urls)) img.remove();
  }
  return template.innerHTML;
}

export function referencedImageIds(html: string): number[] {
  return [...html.matchAll(STORED_SRC_RE)].map((match) => Number(match[1]));
}

/** Object URLs of a broadcast's email images, each fetched once and revoked on unmount.
 *  An image that fails to load maps to "" so the editor doesn't wait on it. */
export function useEmailImageUrls(broadcastId: number | null, ids: number[]) {
  const [urls, setUrls] = useState<Record<number, string>>({});
  const requested = useRef(new Set<number>());
  const created = useRef<string[]>([]);
  const idsKey = ids.join(",");

  const add = useCallback((id: number, url: string) => {
    requested.current.add(id);
    if (url) created.current.push(url);
    setUrls((current) => ({ ...current, [id]: url }));
  }, []);

  useEffect(() => {
    if (broadcastId === null) return;
    for (const id of idsKey ? idsKey.split(",").map(Number) : []) {
      if (requested.current.has(id)) continue;
      requested.current.add(id);
      fetchEmailImage(broadcastId, id).then(
        (blob) => add(id, URL.createObjectURL(blob)),
        () => add(id, ""),
      );
    }
  }, [broadcastId, idsKey, add]);

  useEffect(() => () => created.current.forEach((url) => URL.revokeObjectURL(url)), []);

  const ready = broadcastId === null || ids.every((id) => id in urls);
  return { urls, ready, add };
}
