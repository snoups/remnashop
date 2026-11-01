import { motion, type HTMLMotionProps } from "motion/react";
import type { KeyboardEvent, ReactNode } from "react";
import type { To } from "react-router-dom";

import { MotionLink } from "@shared/ui/MotionLink";
import { Ripple } from "@shared/ui/Ripple";
import { rippleHost } from "@shared/ui/ripple-host";

type Base = { className?: string; children?: ReactNode };

type PressableProps =
  | (Base & { as?: "button" } & Omit<HTMLMotionProps<"button">, "children" | "className">)
  | (Base & { as: "a" } & Omit<HTMLMotionProps<"a">, "children" | "className">)
  | (Base & { as: "link"; to: To } & Omit<HTMLMotionProps<"a">, "children" | "className" | "href">)
  /** a row that holds controls of its own (a switch, a link), which a <button> can't contain */
  | (Base & { as: "div"; disabled?: boolean } & Omit<HTMLMotionProps<"div">, "children" | "className">);

/**
 * The one thing that knows about pressing: positions the element and puts the tap ripple in it, so the shared
 * buttons, rows and links built on it never repeat that. No look of its own; className is the whole style.
 */
export function Pressable(props: PressableProps) {
  const host = rippleHost(props.className ?? "");
  const className = `${host} ${props.className ?? ""}`;

  if (props.as === "a") {
    const { as: _as, className: _className, children, ...rest } = props;
    return (
      <motion.a className={className} {...rest}>
        <Ripple />
        {children}
      </motion.a>
    );
  }
  if (props.as === "link") {
    const { as: _as, className: _className, children, ...rest } = props;
    return (
      <MotionLink className={className} {...rest}>
        <Ripple />
        {children}
      </MotionLink>
    );
  }
  if (props.as === "div") {
    const { as: _as, className: _className, children, disabled = false, onClick, onKeyDown, ...rest } = props;
    // Enter and Space press it like a button; a key pressed on a control inside stays that control's
    const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
      onKeyDown?.(event);
      if (disabled || event.defaultPrevented || event.target !== event.currentTarget) return;
      if (event.key !== "Enter" && event.key !== " ") return;
      event.preventDefault();
      event.currentTarget.click();
    };
    return (
      <motion.div
        tabIndex={disabled ? -1 : 0}
        data-disabled={disabled || undefined}
        onClick={disabled ? undefined : onClick}
        onKeyDown={handleKeyDown}
        className={`${className} ${disabled ? "" : "cursor-pointer"}`}
        {...rest}
      >
        {!disabled && <Ripple />}
        {children}
      </motion.div>
    );
  }
  const { as: _as, className: _className, children, type = "button", ...rest } = props;
  return (
    <motion.button type={type} className={className} {...rest}>
      <Ripple />
      {children}
    </motion.button>
  );
}
