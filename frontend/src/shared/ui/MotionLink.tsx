import { motion } from "motion/react";
import type { HTMLMotionProps } from "motion/react";
import { useHref, useLinkClickHandler } from "react-router-dom";
import type { To } from "react-router-dom";

// Not motion.create(Link): Link hands its element a new merged ref on every
// render, so Motion remounts and a hover or tap in progress never ends.
export function MotionLink({ to, onClick, ...props }: Omit<HTMLMotionProps<"a">, "href"> & { to: To }) {
  const href = useHref(to);
  const navigate = useLinkClickHandler<HTMLAnchorElement>(to);
  return (
    <motion.a
      href={href}
      onClick={(event) => {
        onClick?.(event);
        if (!event.defaultPrevented) navigate(event);
      }}
      {...props}
    />
  );
}
