import { Eye, EyeOff } from "lucide-react";
import { motion } from "motion/react";
import { useState, type ComponentProps } from "react";

import { bounceTap } from "@shared/lib/bounceState";
import { TextInput } from "@shared/ui/TextInput";

/** TextInput with a show/hide eye; className sizes the wrapper. */
export function PasswordInput({ className = "", ...props }: Omit<ComponentProps<typeof TextInput>, "type">) {
  const [isVisible, setIsVisible] = useState(false);
  return (
    <div className={`relative ${className}`}>
      <TextInput {...props} type={isVisible ? "text" : "password"} className="w-full pr-10" />
      <motion.button
        type="button"
        onClick={() => setIsVisible((value) => !value)}
        tabIndex={-1}
        {...bounceTap(0.12)}
        className="absolute inset-y-0 right-0 flex items-center px-3 text-foreground/50 hover:text-foreground"
      >
        {isVisible ? <EyeOff size={16} /> : <Eye size={16} />}
      </motion.button>
    </div>
  );
}
