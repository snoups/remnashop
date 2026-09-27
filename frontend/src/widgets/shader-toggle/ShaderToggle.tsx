import { Zap, ZapOff } from "lucide-react";
import { motion } from "motion/react";
import { useTranslation } from "react-i18next";

import { useAppearance } from "@entities/appearance/use-appearance";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { toggleShaderMuted, useShaderMuted } from "@shared/lib/shader-mute";
import { Tooltip } from "@shared/ui/Tooltip";

export function ShaderToggle() {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const state = useAppearance();
  const muted = useShaderMuted();

  // Nothing to toggle when the shader is off dashboard-wide.
  if (state.kind === "ready" && !state.data.shader_enabled) return null;

  const label = t(muted ? "header.shaderOn" : "header.shaderOff");

  return (
    <motion.button
      type="button"
      onClick={toggleShaderMuted}
      aria-pressed={muted}
      aria-label={label}
      {...bounceTap(bounceStrength, 0.12)}
      className="group relative flex size-9 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] text-muted-foreground transition-colors hover:bg-white/[0.08] hover:text-foreground"
    >
      {muted ? <ZapOff className="size-[17px]" /> : <Zap className="size-[17px]" />}
      <Tooltip text={label} />
    </motion.button>
  );
}
