import { useEffect } from "react";

export function useDocumentTitle(brandName: string, pageTitle: string): void {
  useEffect(() => {
    document.title = `${brandName} — ${pageTitle}`;
  }, [brandName, pageTitle]);
}
