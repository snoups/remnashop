// Every locale must have the same keys as en, every plural form its language needs,
// and the same {{variables}} as the en string.
import { readdirSync, readFileSync } from "node:fs";

const DIR = new URL("../src/shared/i18n/locales/", import.meta.url);
const BASE = "en";
const PLURAL_SUFFIX = /_(zero|one|two|few|many|other)$/;

function flatten(node, prefix = "", out = {}) {
  for (const [key, value] of Object.entries(node)) {
    const path = prefix ? `${prefix}.${key}` : key;
    if (value !== null && typeof value === "object" && !Array.isArray(value)) flatten(value, path, out);
    else out[path] = value;
  }
  return out;
}

function variables(value) {
  return [...JSON.stringify(value).matchAll(/\{\{\s*(\w+)/g)].map((m) => m[1]);
}

// "a.b_one", "a.b_other" -> { "a.b": { forms: Set, vars } }
function group(flat) {
  const out = {};
  for (const [key, value] of Object.entries(flat)) {
    const match = key.match(PLURAL_SUFFIX);
    const base = match ? key.slice(0, match.index) : key;
    out[base] ??= { forms: new Set(), vars: new Set() };
    if (match) out[base].forms.add(match[1]);
    for (const name of variables(value)) out[base].vars.add(name);
  }
  return out;
}

const locales = Object.fromEntries(
  readdirSync(DIR)
    .filter((file) => file.endsWith(".json"))
    .map((file) => [file.slice(0, -5), group(flatten(JSON.parse(readFileSync(new URL(file, DIR), "utf8"))))]),
);

const errors = [];
const base = locales[BASE];
for (const [lang, keys] of Object.entries(locales)) {
  const required = new Intl.PluralRules(lang).resolvedOptions().pluralCategories;
  for (const [key, entry] of Object.entries(keys)) {
    if (!(key in base)) errors.push(`${lang}: extra key ${key}`);
    if (entry.forms.size > 0) {
      const missing = required.filter((form) => !entry.forms.has(form));
      if (missing.length > 0) errors.push(`${lang}: ${key} lacks plural forms ${missing.join(", ")}`);
    }
  }
  if (lang === BASE) continue;
  for (const [key, entry] of Object.entries(base)) {
    if (!(key in keys)) errors.push(`${lang}: missing key ${key}`);
    else if ([...keys[key].vars].sort().join() !== [...entry.vars].sort().join())
      errors.push(`${lang}: ${key} variables differ from ${BASE}`);
  }
}

if (errors.length > 0) {
  console.error(errors.join("\n"));
  process.exit(1);
}
