import { HINT_BUBBLE_CLASS } from "@shared/ui/hint-bubble";

const SIDE_CLASSNAME = {
  right: "left-full top-1/2 ml-3.5 -translate-y-1/2",
  // for a control inside an overflow-hidden panel with no room to its right
  bottom: "left-0 top-full mt-2",
  // the last control in a row at the right edge: the bubble grows leftward from its right side
  "bottom-end": "right-0 top-full mt-2",
  top: "bottom-full left-1/2 mb-2 -translate-x-1/2",
  // top, for items at the edge of a clipping container
  "top-start": "bottom-full left-0 mb-2",
  "top-end": "bottom-full right-0 mb-2",
} as const;

// sits inside the control it describes, which needs `group relative`
export function Tooltip({ text, side = "right" }: { text: string; side?: keyof typeof SIDE_CLASSNAME }) {
  return (
    <span
      className={`${HINT_BUBBLE_CLASS} z-50 whitespace-pre-line ${SIDE_CLASSNAME[side]} group-hover:opacity-100 group-focus-visible:opacity-100`}
    >
      {text}
    </span>
  );
}
