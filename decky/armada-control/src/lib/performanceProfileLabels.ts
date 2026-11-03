import { translateLabelForLocale, type Locale } from "../i18n";

export type PerformanceProfileOption = {
  data?: unknown;
  label?: unknown;
};

const NATIVE_PROFILE_IDS = ["Eco", "Balanced", "Performance"] as const;
const NATIVE_PROFILE_ID_SET: ReadonlySet<string> = new Set(NATIVE_PROFILE_IDS);

export function localizePerformanceProfileOptions<T extends PerformanceProfileOption>(
  options: T[] | undefined,
  locale: Locale,
): T[] | undefined {
  if (!options || locale === "en") return options;
  let changed = false;
  const localized = options.map((option) => {
    if (!option || typeof option.data !== "string"
      || !NATIVE_PROFILE_ID_SET.has(option.data) || option.label !== option.data) {
      return option;
    }
    const label = translateLabelForLocale(locale, option.data);
    if (label === option.label) return option;
    changed = true;
    return { ...option, label } as T;
  });
  return changed ? localized : options;
}
