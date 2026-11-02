import { motion } from "motion/react";

interface SwitchProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
}

/** 48×28 switch; off it is a sunken well like the fields. data-switch: Row gives it its own end inset. */
export function Switch({ checked, onChange, disabled = false }: SwitchProps) {
  return (
    <button
      type="button"
      data-switch
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`relative h-7 w-12 shrink-0 rounded-full transition-colors duration-200 disabled:cursor-not-allowed disabled:opacity-40 ${
        checked ? "bg-primary shadow-[inset_0_1px_0_rgb(255_255_255/0.35)]" : "glass-well"
      }`}
    >
      {/* 24px knob 2px in, 20px of travel; held, it stretches 6px toward the middle like a drop */}
      <motion.span
        className="absolute left-0.5 top-0.5 size-6 rounded-full bg-white shadow-[0_2px_6px_rgb(0_0_0/0.35)]"
        animate={{ x: checked ? 20 : 0, width: 24 }}
        whileTap={{ x: checked ? 14 : 0, width: 30 }}
        transition={{ type: "spring", stiffness: 520, damping: 32 }}
      />
    </button>
  );
}
