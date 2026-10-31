import { translateLabelForLocale, type Locale } from "../i18n";

export type PerformanceProfileOption = {
  data?: unknown;
  label?: unknown;
};

const NATIVE_PROFILE_IDS = ["Eco", "Balanced", "Performance"] as const;
const NATIVE_PROFILE_ID_SET: ReadonlySet<string> = new Set(NATIVE_PROFILE_IDS);

// Only Steam's own profile dropdown has exactly these three self-labelled IDs.
function isNativeProfileDropdown(options: PerformanceProfileOption[]): boolean {
  if (options.length !== NATIVE_PROFILE_IDS.length) return false;
  const seen = new Set<string>();
  for (const option of options) {
    if (!option || typeof option !== "object") return false;
    if (typeof option.data !== "string" || option.label !== option.data) return false;
    if (!NATIVE_PROFILE_ID_SET.has(option.data)) return false;
    seen.add(option.data);
  }
  return seen.size === NATIVE_PROFILE_IDS.length;
}

export function localizePerformanceProfileOptions<T extends PerformanceProfileOption>(
  options: T[] | undefined,
  locale: Locale,
): T[] | undefined {
  if (!options || !isNativeProfileDropdown(options)) return options;
  let changed = false;
  const localized = options.map((option) => {
    const label = translateLabelForLocale(locale, String(option.label));
    if (label === option.label) return option;
    changed = true;
    return { ...option, label } as T;
  });
  return changed ? localized : options;
}
