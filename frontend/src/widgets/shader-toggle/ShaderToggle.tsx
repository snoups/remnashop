import { Zap, ZapOff } from "lucide-react";
import { useTranslation } from "react-i18next";

import { useAppearance } from "@entities/appearance/use-appearance";
import { toggleShaderMuted, useShaderMuted } from "@shared/lib/shader-mute";
import { Tooltip } from "@shared/ui/Tooltip";
import { IconButton } from "@shared/ui/IconButton";

export function ShaderToggle() {
  const { t } = useTranslation();
  const state = useAppearance();
  const muted = useShaderMuted();

  // Nothing to toggle when the shader is off dashboard-wide.
  if (state.kind === "ready" && !state.data.shader_enabled) return null;

  const label = t(muted ? "header.shaderOn" : "header.shaderOff");

  return (
    <IconButton
      size="9"
      tone="glass"
      bounce={0.12}
      className="group relative"
      onClick={toggleShaderMuted}
    >
      {muted ? <ZapOff className="size-[17px]" /> : <Zap className="size-[17px]" />}
      <Tooltip text={label} />
    </IconButton>
  );
}
