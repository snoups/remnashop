import { createContext, useContext } from "react";

/** A required Field's control is required too: the star and the browser's check can't drift apart. */
export const FieldRequiredContext = createContext(false);

const NON_BLANK_PATTERN = ".*\\S.*";

/** For an input in a required Field: spaces alone don't pass. A textarea has no pattern attribute. */
export function useRequiredInputProps(): { required?: true; pattern?: string } {
  return useContext(FieldRequiredContext) ? { required: true, pattern: NON_BLANK_PATTERN } : {};
}
