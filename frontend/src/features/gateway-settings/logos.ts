const files = import.meta.glob<string>("./logos/*.{png,svg}", { eager: true, import: "default" });

// keyed by gateway type: ./logos/YOOKASSA.png -> YOOKASSA
export const GATEWAY_LOGOS: Readonly<Record<string, string>> = Object.fromEntries(
  Object.entries(files).map(([path, url]) => [path.slice("./logos/".length).replace(/\.\w+$/, ""), url]),
);
