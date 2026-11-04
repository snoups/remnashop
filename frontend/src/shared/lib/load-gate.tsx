import { createContext, useContext, useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";

// a slow request shouldn't keep the page blank: past this it shows, spinners and all
const MAX_HOLD_MS = 500;

// the last answers land as the gate opens: sizes changing this soon after are the first layout
const SETTLE_MS = 100;

interface LoadGateValue {
  hold: () => () => void;
  isSettling: () => boolean;
}

const LoadGateContext = createContext<LoadGateValue | null>(null);
// outside a LoadGate there's nothing to wait for
const LoadGateOpenContext = createContext(true);

const NEVER_SETTLING = () => false;

/** Whether the surrounding LoadGate is still laying its content out; stable, false outside one. */
export function useLoadGateSettling(): () => boolean {
  return useContext(LoadGateContext)?.isSettling ?? NEVER_SETTLING;
}

/** Whether the surrounding LoadGate has faded its content in; true outside one. For an entrance
 *  animation that would otherwise play out unseen. */
export function useLoadGateOpen(): boolean {
  return useContext(LoadGateOpenContext);
}

/** Keeps the surrounding LoadGate closed while `isLoading`; does nothing outside one. */
export function useLoadGateHold(isLoading: boolean): void {
  const hold = useContext(LoadGateContext)?.hold;
  useLayoutEffect(() => {
    if (isLoading && hold) return hold();
  }, [isLoading, hold]);
}

/** useLoadGateHold for a page whose loads run above its own LoadGate: rendered inside, holds it. */
export function LoadGateHold({ isLoading }: { isLoading: boolean }) {
  useLoadGateHold(isLoading);
  return null;
}

/** Lays its content out unseen until every first load inside has settled, then fades it in,
 *  so cards growing one by one as their answers arrive aren't watched. */
export function LoadGate({ children }: { children: ReactNode }) {
  const [isOpen, setIsOpen] = useState(false);
  const holdsRef = useRef(0);
  const openedAtRef = useRef<number | null>(null);

  const open = () => {
    openedAtRef.current ??= performance.now();
    setIsOpen(true);
  };

  // a microtask: a card that just loaded may mount a child whose own hold lands later in this commit
  const openIfSettled = () =>
    queueMicrotask(() => {
      if (holdsRef.current === 0) open();
    });

  const valueRef = useRef<LoadGateValue>({
    hold: () => {
      holdsRef.current += 1;
      return () => {
        holdsRef.current -= 1;
        openIfSettled();
      };
    },
    isSettling: () => openedAtRef.current === null || performance.now() - openedAtRef.current < SETTLE_MS,
  });

  // nothing inside loads anything
  useLayoutEffect(openIfSettled, []);

  useEffect(() => {
    const timer = setTimeout(open, MAX_HOLD_MS);
    return () => clearTimeout(timer);
  }, []);

  return (
    <LoadGateContext.Provider value={valueRef.current}>
      <LoadGateOpenContext.Provider value={isOpen}>
        <div className={`transition-opacity duration-200 ease-out ${isOpen ? "opacity-100" : "pointer-events-none opacity-0"}`}>
          {children}
        </div>
      </LoadGateOpenContext.Provider>
    </LoadGateContext.Provider>
  );
}
