import { useEffect, useState } from "react";
import {
  detectLocaleFromEnvironment,
  resolveLocale,
  setCurrentLocale,
} from "../i18n";
import type { Locale } from "../i18n";

export function useLocale(): Locale {
  const [locale, setLocale] = useState<Locale>(() => {
    const initial = detectLocaleFromEnvironment();
    setCurrentLocale(initial);
    return initial;
  });

  useEffect(() => {
    let cancelled = false;
    const refresh = async () => {
      try {
        const steamLanguage = await window.SteamClient?.Settings?.GetCurrentLanguage?.();
        const next = resolveLocale({
          steamLanguage,
          deckyLocales: window.LocalizationManager?.m_rgLocalesToUse,
          browserLanguages: navigator.languages || [navigator.language],
        });
        if (cancelled) return;
        setCurrentLocale(next);
        setLocale(next);
      } catch (error) {
      }
    };
    void refresh();
    return () => {
      cancelled = true;
    };
  }, []);

  return locale;
}
