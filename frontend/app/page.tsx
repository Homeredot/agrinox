"use client";

import { useEffect, useState } from "react";
import AuthPanel from "@/components/AuthPanel";
import Dashboard from "@/components/Dashboard";
import I18nProvider from "@/components/I18nProvider";
import ThemeProvider from "@/components/ThemeProvider";
import { Language } from "@/lib/i18n";
import { api } from "@/lib/api";

export default function Home() {
  const [ready,setReady]=useState(false); const [token,setToken]=useState<string|null>(null); const [language,setLanguageState]=useState<Language>("en");
  useEffect(()=>{const savedToken=localStorage.getItem("agrinox_token");const savedLanguage=localStorage.getItem("agrinox_language") as Language|null;setToken(savedToken);setLanguageState(savedLanguage||"en");setReady(true)},[]);
  function setLanguage(value:Language){setLanguageState(value);localStorage.setItem("agrinox_language",value);if(token)void api("/auth/me/language",{method:"PATCH",body:JSON.stringify({preferred_language:value})},token).catch(()=>undefined)}
  if(!ready)return null;
  if(!token)return <ThemeProvider><I18nProvider language={language}><button aria-label="Change language" onClick={()=>setLanguage(language==="en"?"rw":"en")} className="auth-language-toggle fixed top-5 right-5 z-40 min-h-11 rounded-xl border px-4 py-2 text-sm font-bold shadow-lg backdrop-blur">{language==="en"?"Kinyarwanda":"English"}</button><AuthPanel language={language} onAuth={setToken}/></I18nProvider></ThemeProvider>;
  return <ThemeProvider><I18nProvider language={language}><Dashboard token={token} language={language} setLanguage={setLanguage} onLogout={()=>{localStorage.removeItem("agrinox_token");setToken(null)}}/></I18nProvider></ThemeProvider>;
}

