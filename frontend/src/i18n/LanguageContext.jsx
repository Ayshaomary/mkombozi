import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { translations } from './translations'

const LANG_KEY = 'mukombozi_lang'
const LanguageContext = createContext(null)

function savedLanguage() {
  try {
    return localStorage.getItem(LANG_KEY) || 'sw'
  } catch {
    return 'sw'
  }
}

export function LanguageProvider({ children }) {
  const [lang, setLangState] = useState(savedLanguage)

  useEffect(() => {
    document.documentElement.lang = lang
  }, [lang])

  const setLang = (value) => {
    setLangState(value)
    try {
      localStorage.setItem(LANG_KEY, value)
    } catch {
      // Not saved; the language resets to Kiswahili next visit
    }
  }

  // t('nav.sales') -> 'Mauzo';  t('dashboard.greeting', { name: 'Amina' }) -> 'Habari, Amina'
  const t = useCallback(
    (key, vars) => {
      const lookup = (dict) => key.split('.').reduce((obj, part) => obj?.[part], dict)
      let text = lookup(translations[lang]) ?? lookup(translations.en) ?? key
      if (vars) {
        for (const [name, value] of Object.entries(vars)) text = text.replaceAll(`{${name}}`, value)
      }
      return text
    },
    [lang],
  )

  return <LanguageContext.Provider value={{ lang, setLang, t }}>{children}</LanguageContext.Provider>
}

export function useLanguage() {
  return useContext(LanguageContext)
}
