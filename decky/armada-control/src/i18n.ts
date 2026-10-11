import { en, type TranslationKey } from "./locales/en";
import { zhCN } from "./locales/zh-CN";
import { ptBR } from "./locales/pt-BR";
import { ptPT } from "./locales/pt-PT";

export type { TranslationKey } from "./locales/en";
type Variables = Record<string, string | number>;

export const localeStrings = {
  en,
  "zh-CN": zhCN,
  "pt-BR": ptBR,
  "pt-PT": ptPT,
} as const satisfies Record<string, Record<TranslationKey, string>>;

export type Locale = keyof typeof localeStrings;

export function localeFromLanguage(language: unknown): Locale | null {
  if (typeof language !== "string") return null;
  const normalized = language.trim().toLowerCase().split("_").join("-");
  if (["schinese", "steamchina-schinese", "zh", "zh-cn", "zh-hans", "zh-sg"].includes(normalized)) return "zh-CN";
  if (["pt-br", "brazilian", "pt-brasil"].includes(normalized)) return "pt-BR";
  if (["pt", "pt-pt", "portuguese"].includes(normalized)) return "pt-PT";
  return normalized ? "en" : null;
}

function firstLocale(values: readonly unknown[] | undefined): Locale | null {
  for (const value of values || []) {
    const locale = localeFromLanguage(value);
    if (locale) return locale;
  }
  return null;
}

export function resolveLocale({
  steamLanguage,
  deckyLocales,
  browserLanguages,
}: {
  steamLanguage?: unknown;
  deckyLocales?: readonly unknown[];
  browserLanguages?: readonly unknown[];
}): Locale {
  return localeFromLanguage(steamLanguage)
    || firstLocale(deckyLocales)
    || firstLocale(browserLanguages)
    || "en";
}

export function detectLocaleFromEnvironment(): Locale {
  let deckyLocales: readonly unknown[] | undefined;
  let browserLanguages: readonly unknown[] | undefined;
  try {
    deckyLocales = window.LocalizationManager?.m_rgLocalesToUse;
  } catch (error) {
  }
  try {
    browserLanguages = navigator.languages || [navigator.language];
  } catch (error) {
  }
  return resolveLocale({ deckyLocales, browserLanguages });
}

let currentLocale: Locale = "en";

export function setCurrentLocale(locale: Locale): void {
  currentLocale = locale;
}

// Modals open through showModal, outside the tree useLocale() feeds.
export function getCurrentLocale(): Locale {
  return currentLocale;
}

function interpolate(text: string, variables?: Variables): string {
  if (!variables) return text;
  return Object.entries(variables).reduce(
    (result, [key, value]) => result.split(`{${key}}`).join(String(value)),
    text,
  );
}

export function translate(locale: Locale, key: TranslationKey, variables?: Variables): string {
  return interpolate(localeStrings[locale][key], variables);
}

export function t(key: TranslationKey, variables?: Variables): string {
  return translate(currentLocale, key, variables);
}

const translationKeyByEnglishLabel = Object.fromEntries(
  Object.entries(en).map(([key, value]) => [value, key]),
) as Record<string, TranslationKey>;

export function translateLabelForLocale(locale: Locale, label: string): string {
  if (locale === "en") return label;
  const exactKey = translationKeyByEnglishLabel[label];
  if (exactKey) return localeStrings[locale][exactKey];
  for (const prefixKey of ["options.bigCores", "options.primeCores", "options.littleCores"] as const) {
    const englishPrefix = en[prefixKey];
    if (label.startsWith(`${englishPrefix} (`)) {
      return label.replace(englishPrefix, localeStrings[locale][prefixKey]);
    }
  }
  return label;
}

export function translateLabel(label: string): string {
  return translateLabelForLocale(currentLocale, label);
}
