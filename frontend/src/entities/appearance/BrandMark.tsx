import { appearanceImageUrl } from "@entities/appearance/api";
import { BrandLogo } from "@shared/ui/BrandLogo";

import { useAppearance } from "./use-appearance";

export function BrandMark({ className }: { className?: string }) {
  const state = useAppearance();
  const hasLogo = state.kind === "ready" && state.data.has_logo;

  if (hasLogo) {
    return <img src={appearanceImageUrl("dashboard", "logo")} alt="" className={`${className ?? ""} object-contain`} />;
  }
  return <BrandLogo className={className} />;
}
