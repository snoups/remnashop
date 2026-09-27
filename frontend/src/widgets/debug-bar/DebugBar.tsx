import {
  Bell,
  BellRing,
  ClipboardCopy,
  Eraser,
  KeyRound,
  Languages,
  PackagePlus,
  ServerCrash,
  ShieldOff,
  Turtle,
  Wifi,
  WifiOff,
} from "lucide-react";
import { motion } from "motion/react";
import type { ComponentType } from "react";
import { useTranslation } from "react-i18next";

import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import {
  setDebugState,
  useDebugState,
  type ApiFailureMode,
  type LatencyMode,
} from "@shared/lib/debug-bar";
import { toast } from "@shared/lib/toast";
import type { ToastVariant } from "@shared/lib/toast";
import { getSessionId, saveAccessToken } from "@shared/lib/token-storage";
import { Tooltip } from "@shared/ui/Tooltip";
import { ShaderToggle } from "@widgets/shader-toggle/ShaderToggle";

const VARIANTS: ToastVariant[] = ["info", "success", "warning", "error"];

const FAILURE_CYCLE: Record<ApiFailureMode, ApiFailureMode> = {
  off: "network",
  network: "server",
  server: "off",
};

const FAILURE_ICON: Record<ApiFailureMode, ComponentType<{ className?: string }>> = {
  off: Wifi,
  network: WifiOff,
  server: ServerCrash,
};

const LATENCY_CYCLE: Record<LatencyMode, LatencyMode> = { 0: 2000, 2000: 10000, 10000: 0 };

let next = 0;

function DebugButton({
  icon: Icon,
  label,
  active,
  onClick,
}: {
  icon: ComponentType<{ className?: string }>;
  label: string;
  active?: boolean;
  onClick: () => void;
}) {
  const bounceStrength = useBounceStrength();

  return (
    <motion.button
      type="button"
      onClick={onClick}
      aria-label={label}
      aria-pressed={active}
      {...bounceTap(bounceStrength, 0.12)}
      className={`group relative flex size-9 shrink-0 items-center justify-center rounded-full border border-glass-border transition-colors ${
        active
          ? "bg-accent text-primary"
          : "bg-white/[0.05] text-muted-foreground hover:bg-white/[0.08] hover:text-foreground"
      }`}
    >
      <Icon className="size-[17px]" />
      <Tooltip text={label} />
    </motion.button>
  );
}

export function DebugBar() {
  const { t, i18n } = useTranslation();
  const state = useDebugState();
  const { barVisible, apiFailure, latency, noPermissions, fakeUpdate, missingKeys } = state;

  if (!barVisible) return null;

  const sendToast = () => {
    const variant = VARIANTS[next++ % VARIANTS.length];
    toast[variant](t("debugBar.testToastMessage", { variant }));
  };

  const burstToasts = () => {
    VARIANTS.forEach((variant) => toast[variant](t("debugBar.testToastMessage", { variant })));
    toast.info(t("debugBar.testToastLong"));
  };

  const expireToken = () => {
    saveAccessToken("debug.expired.token");
    toast.info(t("debugBar.tokenExpired"));
  };

  const wipeStorage = () => {
    localStorage.clear();
    window.location.reload();
  };

  const copySnapshot = () => {
    const snapshot = {
      url: window.location.href,
      viewport: `${window.innerWidth}x${window.innerHeight}`,
      language: i18n.language,
      sessionId: getSessionId(),
      userAgent: navigator.userAgent,
      debug: state,
    };
    navigator.clipboard
      ?.writeText(JSON.stringify(snapshot, null, 2))
      .then(() => toast.success(t("debugBar.snapshotCopied")))
      .catch(() => toast.error(t("debugBar.snapshotFailed")));
  };

  return (
    <div className="fixed bottom-4 left-4 z-50 flex flex-col items-center gap-2 rounded-full border border-glass-border bg-popover/50 p-1.5 backdrop-blur-2xl backdrop-saturate-150">
      <ShaderToggle />
      <DebugButton icon={Bell} label={t("debugBar.testToast")} onClick={sendToast} />
      <DebugButton icon={BellRing} label={t("debugBar.burstToasts")} onClick={burstToasts} />
      <DebugButton
        icon={FAILURE_ICON[apiFailure]}
        label={t(`debugBar.apiFailure.${apiFailure}`)}
        active={apiFailure !== "off"}
        onClick={() => setDebugState({ apiFailure: FAILURE_CYCLE[apiFailure] })}
      />
      <DebugButton
        icon={Turtle}
        label={t(latency ? "debugBar.latency.on" : "debugBar.latency.off", { seconds: latency / 1000 })}
        active={latency !== 0}
        onClick={() => setDebugState({ latency: LATENCY_CYCLE[latency] })}
      />
      <DebugButton icon={KeyRound} label={t("debugBar.expireToken")} onClick={expireToken} />
      <DebugButton
        icon={ShieldOff}
        label={t("debugBar.noPermissions")}
        active={noPermissions}
        onClick={() => setDebugState({ noPermissions: !noPermissions })}
      />
      <DebugButton
        icon={PackagePlus}
        label={t("debugBar.fakeUpdate")}
        active={fakeUpdate}
        onClick={() => setDebugState({ fakeUpdate: !fakeUpdate })}
      />
      <DebugButton
        icon={Languages}
        label={t("debugBar.missingKeys")}
        active={missingKeys}
        onClick={() => setDebugState({ missingKeys: !missingKeys })}
      />
      <DebugButton icon={ClipboardCopy} label={t("debugBar.copySnapshot")} onClick={copySnapshot} />
      <DebugButton icon={Eraser} label={t("debugBar.wipeStorage")} onClick={wipeStorage} />
    </div>
  );
}
