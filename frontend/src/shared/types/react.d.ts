import "react";

// Safari's non-standard "Password Rules" attribute: tells the browser's
// built-in password generator what to produce. Not in React's DOM typings.
declare module "react" {
  interface InputHTMLAttributes<T> {
    passwordrules?: string;
  }
}
