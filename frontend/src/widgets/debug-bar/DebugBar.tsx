import {
  Bell,
  BellRing,
  ChevronsDownUp,
  ChevronsUpDown,
  ClipboardCopy,
  Eraser,
  FlaskConical,
  KeyRound,
  Languages,
  PackagePlus,
  ServerCrash,
  ShieldOff,
  Turtle,
  Wifi,
  WifiOff,
  X,
} from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import type { ComponentType, ReactNode } from "react";
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

const BAR_TRANSITION = { duration: 0.22, ease: [0.2, 0.8, 0.2, 1] } as const;

let next = 0;

function DebugButton({
  icon: Icon,
  label,
  active,
  onClick,
  className = "",
}: {
  icon: ComponentType<{ className?: string }>;
  label: string;
  active?: boolean;
  onClick: () => void;
  className?: string;
}) {
  const bounceStrength = useBounceStrength();

  return (
    <motion.button
      type="button"
      onClick={onClick}
      aria-label={label}
      aria-pressed={active}
      {...bounceTap(bounceStrength, 0.12)}
      className={`${className} group relative flex size-9 shrink-0 items-center justify-center rounded-full border border-glass-border transition-colors ${
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
  const { barVisible, barCollapsed, apiFailure, latency, noPermissions, fakeUpdate, missingKeys } = state;

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

  // Stateful switches -- the ones left on stay visible while the bar is collapsed.
  const toggles = [
    {
      key: "apiFailure",
      icon: FAILURE_ICON[apiFailure],
      label: t(`debugBar.apiFailure.${apiFailure}`),
      active: apiFailure !== "off",
      onClick: () => setDebugState({ apiFailure: FAILURE_CYCLE[apiFailure] }),
    },
    {
      key: "latency",
      icon: Turtle,
      label: t(latency ? "debugBar.latency.on" : "debugBar.latency.off", { seconds: latency / 1000 }),
      active: latency !== 0,
      onClick: () => setDebugState({ latency: LATENCY_CYCLE[latency] }),
    },
    {
      key: "noPermissions",
      icon: ShieldOff,
      label: t("debugBar.noPermissions"),
      active: noPermissions,
      onClick: () => setDebugState({ noPermissions: !noPermissions }),
    },
    {
      key: "fakeUpdate",
      icon: PackagePlus,
      label: t("debugBar.fakeUpdate"),
      active: fakeUpdate,
      onClick: () => setDebugState({ fakeUpdate: !fakeUpdate }),
    },
    {
      key: "missingKeys",
      icon: Languages,
      label: t("debugBar.missingKeys"),
      active: missingKeys,
      onClick: () => setDebugState({ missingKeys: !missingKeys }),
    },
  ];
  const toggleItems = toggles.map(({ key, ...toggle }) => ({ key, node: <DebugButton {...toggle} /> }));
  const divider = { key: "divider", node: <span aria-hidden className="block h-px w-6 bg-glass-border" /> };

  const items: { key: string; node: ReactNode }[] = barCollapsed
    ? [
        ...(toggles.some((toggle) => toggle.active) ? [divider] : []),
        ...toggleItems.filter((_, i) => toggles[i].active),
        {
          key: "expand",
          node: (
            <DebugButton
              icon={ChevronsUpDown}
              label={t("debugBar.expand")}
              onClick={() => setDebugState({ barCollapsed: false })}
            />
          ),
        },
      ]
    : [
        divider,
        { key: "shader", node: <ShaderToggle /> },
        { key: "toast", node: <DebugButton icon={Bell} label={t("debugBar.testToast")} onClick={sendToast} /> },
        { key: "burst", node: <DebugButton icon={BellRing} label={t("debugBar.burstToasts")} onClick={burstToasts} /> },
        ...toggleItems.slice(0, 2),
        {
          key: "expireToken",
          node: <DebugButton icon={KeyRound} label={t("debugBar.expireToken")} onClick={expireToken} />,
        },
        ...toggleItems.slice(2),
        {
          key: "debugPage",
          // full navigation: the bar renders outside the router, so no client-side navigate here
          node: (
            <DebugButton
              icon={FlaskConical}
              label={t("debugBar.openDebugPage")}
              onClick={() => window.location.assign("/dashboard/debug")}
            />
          ),
        },
        {
          key: "snapshot",
          node: <DebugButton icon={ClipboardCopy} label={t("debugBar.copySnapshot")} onClick={copySnapshot} />,
        },
        { key: "wipe", node: <DebugButton icon={Eraser} label={t("debugBar.wipeStorage")} onClick={wipeStorage} /> },
        {
          key: "collapse",
          node: (
            <DebugButton
              icon={ChevronsDownUp}
              label={t("debugBar.collapse")}
              onClick={() => setDebugState({ barCollapsed: true })}
            />
          ),
        },
      ];

  return (
    // desktop only -- no way to open it on mobile anyway.
    // borderRadius inline, not rounded-full -- motion only corrects layout distortion for style values.
    <motion.div
      layout
      transition={BAR_TRANSITION}
      style={{ borderRadius: 9999 }}
      className="fixed bottom-4 left-4 z-50 hidden flex-col-reverse items-center gap-2 border border-glass-border bg-popover/50 p-1.5 backdrop-blur-2xl backdrop-saturate-150 md:flex"
    >
      <motion.div layout="position" transition={BAR_TRANSITION}>
        <DebugButton icon={X} label={t("debugBar.close")} onClick={() => setDebugState({ barVisible: false })} />
      </motion.div>
      <AnimatePresence initial={false} mode="popLayout">
        {items.map(({ key, node }) => (
          <motion.div
            key={key}
            layout="position"
            initial={{ opacity: 0, scale: 0.6 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.6 }}
            transition={BAR_TRANSITION}
            // ShaderToggle renders nothing when the shader is off dashboard-wide
            className="shrink-0 empty:hidden"
          >
            {node}
          </motion.div>
        ))}
      </AnimatePresence>
    </motion.div>
  );
}
