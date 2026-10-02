export function roiClassName(roi: string | null): string {
  if (roi === null) return "text-muted-foreground";
  return Number(roi) >= 0 ? "text-success" : "text-error";
}
