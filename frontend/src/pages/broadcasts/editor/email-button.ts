import { Mark } from "@tiptap/react";

import { EMAIL_URL_RE } from "@pages/broadcasts/editor/email-images";

// a link drawn as a button in the letter; the backend accepts exactly <a data-button="" href="...">
export const EmailButton = Mark.create({
  name: "button",
  inclusive: false,
  // both render as <a>, which can't nest
  excludes: "link",

  addAttributes() {
    return { href: { default: null, parseHTML: (el) => el.getAttribute("href") } };
  },

  parseHTML() {
    // ahead of the link's own a[href] rule
    return [
      {
        tag: "a[data-button][href]",
        priority: 60,
        getAttrs: (el) => (EMAIL_URL_RE.test(el.getAttribute("href") ?? "") ? null : false),
      },
    ];
  },

  renderHTML({ HTMLAttributes }) {
    return ["a", { "data-button": "", href: HTMLAttributes.href as string }, 0];
  },
});
