import type { Locale } from "../i18n";
import type { EnvPreset, LocalizedText } from "../types";

// env-presets.json carries a plain string for a text that needs no translation
// and a map keyed by locale otherwise. English covers a missing locale, because
// an admin adding a variable in /etc/armada only writes the language they speak.
export function localized(text: LocalizedText | undefined, locale: Locale): string {
  if (typeof text === "string") return text;
  return text?.[locale] ?? text?.en ?? "";
}

export const findPreset = (presets: EnvPreset[], name: string): EnvPreset | undefined =>
  presets.find((preset) => preset.name === name);

// What a variable is currently set to, for prefilling the picker. A null in own
// is a tombstone that switches off an inherited variable, so it falls through to
// the global value rather than reading as "set to nothing".
export function resolveEnvValues(
  own: Record<string, string | null>,
  global: Record<string, string>,
): Record<string, string> {
  const values = { ...global };
  for (const [name, value] of Object.entries(own)) if (typeof value === "string") values[name] = value;
  return values;
}
