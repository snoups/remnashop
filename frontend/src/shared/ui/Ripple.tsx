import { useEffect, useRef, useState } from "react";

interface Wave {
  id: number;
  x: number;
  y: number;
  size: number;
}

/**
 * A tap ripple for its parent: drop it inside a positioned button, tab or row, and it answers that element's
 * pointer-down with a wave from the pointer. It clips to a layer that takes the parent's radius, so the parent
 * needs no overflow-hidden (which would clip a pill gliding into it). The point is kept as a share of the
 * element, so a wave stays put while the element resizes. CSS animate-tap-ripple (app/styles.css); none with
 * reduced motion, none from a key, none on a disabled control (it gets no pointer events).
 */
export function Ripple() {
  const layerRef = useRef<HTMLSpanElement>(null);
  const [waves, setWaves] = useState<Wave[]>([]);

  useEffect(() => {
    const host = layerRef.current?.parentElement;
    if (!host) return;
    const onPointerDown = (event: PointerEvent) => {
      const rect = host.getBoundingClientRect();
      // a circle that covers the element from whichever point it starts at
      const size = Math.hypot(rect.width, rect.height) * 2;
      const x = (event.clientX - rect.left) / rect.width;
      const y = (event.clientY - rect.top) / rect.height;
      setWaves((current) => [...current, { id: event.timeStamp, x, y, size }]);
    };
    host.addEventListener("pointerdown", onPointerDown);
    return () => host.removeEventListener("pointerdown", onPointerDown);
  }, []);

  return (
    <span ref={layerRef} className="pointer-events-none absolute inset-0 overflow-hidden rounded-[inherit]">
      {waves.map(({ id, x, y, size }) => (
        <span
          key={id}
          className="absolute hidden rounded-full bg-white/15 motion-safe:block motion-safe:animate-tap-ripple"
          style={{
            left: `calc(${x * 100}% - ${size / 2}px)`,
            top: `calc(${y * 100}% - ${size / 2}px)`,
            width: size,
            height: size,
          }}
          onAnimationEnd={() => setWaves((current) => current.filter((wave) => wave.id !== id))}
        />
      ))}
    </span>
  );
}
