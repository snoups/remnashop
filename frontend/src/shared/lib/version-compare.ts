export function isNewerVersion(latest: string, current: string): boolean {
  const latestParts = latest.replace(/^v/, "").split(".").map(Number);
  const currentParts = current.replace(/^v/, "").split(".").map(Number);

  for (let i = 0; i < Math.max(latestParts.length, currentParts.length); i++) {
    const latestPart = latestParts[i] ?? 0;
    const currentPart = currentParts[i] ?? 0;
    if (latestPart !== currentPart) return latestPart > currentPart;
  }

  return false;
}
