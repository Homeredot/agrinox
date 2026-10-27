"use client";

import { FormEvent, useEffect, useState } from "react";
import { BellRing, CheckCircle2, Contrast, KeyRound, Languages, LoaderCircle, LockKeyhole, Mail, MailCheck, Moon, Palette, ShieldCheck, Smartphone, Sun, X } from "lucide-react";

import { api } from "@/lib/api";
import type { Language } from "@/lib/i18n";
import { useI18n } from "./I18nProvider";
import { type AppTheme, useTheme } from "./ThemeProvider";

type Preferences = { enabled: boolean; calendar_reminders: boolean; irrigation_events: boolean; device_alerts: boolean; soil_alerts: boolean; plant_results: boolean; planning_updates: boolean; finance_updates: boolean; security_updates: boolean; email_configured: boolean };
type TwoFactorStatus = { enabled: boolean; method: "email" | "authenticator" | null; enabled_at?: string | null; email_configured: boolean; masked_email: string };
type Setup = { purpose: "setup" | "disable"; challenge_token: string; method: "email" | "authenticator"; masked_email?: string | null; secret?: string; qr_code_data_url?: string; expires_in_minutes: number };
const categories: Array<[keyof Preferences, string]> = [["calendar_reminders", "notifications.calendar"], ["irrigation_events", "notifications.irrigation"], ["device_alerts", "notifications.devices"], ["soil_alerts", "notifications.soil"], ["plant_results", "notifications.plant"], ["planning_updates", "notifications.planning"], ["finance_updates", "notifications.finance"], ["security_updates", "notifications.security"]];

export default function SettingsPage({ token, language, setLanguage }: { token: string; language: Language; setLanguage: (language: Language) => void }) {
  const { t } = useI18n();
  const { theme, setTheme } = useTheme();
  const [preferences, setPreferences] = useState<Preferences | null>(null);
  const [twoFactor, setTwoFactor] = useState<TwoFactorStatus | null>(null);
  const [setup, setSetup] = useState<Setup | null>(null);
  const [currentPassword, setCurrentPassword] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [passwordBusy, setPasswordBusy] = useState(false);
  const [twoFactorBusy, setTwoFactorBusy] = useState(false);

  useEffect(() => {
    Promise.all([api<Preferences>("/notifications/settings", {}, token), api<TwoFactorStatus>("/auth/2fa/status", {}, token)])
      .then(([nextPreferences, status]) => { setPreferences(nextPreferences); setTwoFactor(status); })
      .catch((requestError) => setError(requestError instanceof Error ? requestError.message : t("common.error")))
      .finally(() => setLoading(false));
  }, [token, t]);

  async function updatePreference(key: keyof Preferences, value: boolean) {
    if (!preferences || key === "email_configured") return;
    const before = preferences; setPreferences({ ...preferences, [key]: value }); setError(""); setMessage("");
    try { setPreferences(await api<Preferences>("/notifications/settings", { method: "PUT", body: JSON.stringify({ [key]: value }) }, token)); setMessage(t("notifications.saved")); }
    catch (requestError) { setPreferences(before); setError(requestError instanceof Error ? requestError.message : t("common.error")); }
  }

  async function beginTwoFactor(method: "email" | "authenticator") {
    if (!currentPassword) { setError(t("twoFactor.passwordNeeded")); return; }
    setTwoFactorBusy(true); setError(""); setMessage("");
    try {
      const result = await api<Omit<Setup, "purpose">>(`/auth/2fa/setup/${method}`, { method: "POST", body: JSON.stringify({ current_password: currentPassword }) }, token);
      setSetup({ ...result, purpose: "setup" }); setCurrentPassword("");
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : t("common.error")); }
    finally { setTwoFactorBusy(false); }
  }

  async function beginDisable() {
    if (!currentPassword) { setError(t("twoFactor.passwordNeeded")); return; }
    setTwoFactorBusy(true); setError(""); setMessage("");
    try {
      const result = await api<Omit<Setup, "purpose">>("/auth/2fa/disable/start", { method: "POST", body: JSON.stringify({ current_password: currentPassword }) }, token);
      setSetup({ ...result, purpose: "disable" }); setCurrentPassword("");
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : t("common.error")); }
    finally { setTwoFactorBusy(false); }
  }

  async function confirmTwoFactor(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!setup) return;
    setTwoFactorBusy(true); setError(""); setMessage("");
    const code = String(new FormData(event.currentTarget).get("code") || "");
    try {
      const endpoint = setup.purpose === "setup" ? "/auth/2fa/setup/confirm" : "/auth/2fa/disable/confirm";
      const status = await api<TwoFactorStatus>(endpoint, { method: "POST", body: JSON.stringify({ challenge_token: setup.challenge_token, code }) }, token);
      setTwoFactor(status); setSetup(null); setMessage(status.enabled ? t("twoFactor.enabledSuccess") : t("twoFactor.disabledSuccess"));
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : t("common.error")); }
    finally { setTwoFactorBusy(false); }
  }

  async function changePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setPasswordBusy(true); setError(""); setMessage("");
    const form = event.currentTarget; const values = Object.fromEntries(new FormData(form));
    if (values.new_password !== values.confirm_password) { setError(t("settings.passwordMismatch")); setPasswordBusy(false); return; }
    try { await api("/auth/me/password", { method: "POST", body: JSON.stringify({ current_password: values.current_password, new_password: values.new_password }) }, token); form.reset(); setMessage(t("settings.passwordChanged")); }
    catch (requestError) { setError(requestError instanceof Error ? requestError.message : t("common.error")); }
    finally { setPasswordBusy(false); }
  }

  return <div className="space-y-6">
    <div><h1 className="text-2xl font-semibold sm:text-4xl">{t("settings.title")}</h1><p className="mobile-secondary mt-2 max-w-2xl text-[#9fa8a1]">{t("settings.subtitle")}</p></div>

    <section className="rounded-3xl border border-[#3a423c] bg-[#222623] p-5 sm:p-7"><SectionTitle icon={<Languages/>} title={t("settings.language")} help={t("settings.languageHelp")}/><div className="mt-5 grid gap-3 sm:grid-cols-2">{(["en", "rw"] as Language[]).map((item) => <button key={item} onClick={() => setLanguage(item)} className={`flex min-h-20 items-center justify-between rounded-2xl border px-5 text-left transition ${language === item ? "border-[#6eaf73] bg-[#2b402e]" : "border-[#414943] bg-[#292e2a] hover:bg-[#303631]"}`}><span><strong className="block">{item === "en" ? t("language.english") : t("language.kinyarwanda")}</strong><small className="mt-1 block text-[#8f9991]">{item === "en" ? "English" : "Kinyarwanda"}</small></span>{language === item && <CheckCircle2 className="text-[#8fd08a]" size={21}/>}</button>)}</div></section>

    <section className="rounded-3xl border border-[#3a423c] bg-[#222623] p-5 sm:p-7">
      <SectionTitle icon={<Palette/>} title={t("settings.appearance")} help={t("settings.appearanceHelp")}/>
      <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {([
          ["grey", Palette, "settings.themeGrey", "settings.themeGreyHelp", "bg-[#343837] border-[#6a716d] text-white"],
          ["dark", Moon, "settings.themeDark", "settings.themeDarkHelp", "bg-[#090c0a] border-[#4d554f] text-white"],
          ["light", Sun, "settings.themeLight", "settings.themeLightHelp", "bg-[#f4f7f1] border-[#bdc8be] text-[#1b251d]"],
          ["contrast", Contrast, "settings.themeContrast", "settings.themeContrastHelp", "bg-black border-white text-white"],
        ] as const).map(([value, Icon, label, help, preview]) => <button key={value} type="button" onClick={() => setTheme(value as AppTheme)} aria-pressed={theme === value} className={`relative min-h-32 rounded-2xl border-2 p-4 text-left transition hover:-translate-y-0.5 ${preview} ${theme === value ? "ring-2 ring-[#83c879] ring-offset-2 ring-offset-[#222623]" : "opacity-85 hover:opacity-100"}`}>
          <span className="flex items-start justify-between gap-3"><Icon size={22}/>{theme === value && <CheckCircle2 size={20} className="text-[#83cf80]"/>}</span>
          <strong className="mt-5 block text-sm">{t(label)}</strong><small className="mt-1 block leading-5 opacity-70">{t(help)}</small>
        </button>)}
      </div>
    </section>

    <section className="rounded-3xl border border-[#3a423c] bg-[#222623] p-5 sm:p-7">
      <SectionTitle icon={<ShieldCheck/>} title={t("twoFactor.title")} help={t("twoFactor.help")}/>
      {loading || !twoFactor ? <LoaderCircle className="mt-6 animate-spin text-[#86c67e]"/> : <div className="mt-5">
        <div className={`flex items-center gap-3 rounded-2xl border p-4 ${twoFactor.enabled ? "border-[#55735a] bg-[#293b2d] text-[#b9dfad]" : "border-[#4a514b] bg-[#292e2a] text-[#c0c7c1]"}`}><ShieldCheck size={21}/><div><strong className="block text-sm">{twoFactor.enabled ? t("twoFactor.on") : t("twoFactor.off")}</strong>{twoFactor.enabled && <small className="mt-1 block opacity-75">{twoFactor.method === "email" ? t("twoFactor.email") : t("twoFactor.authenticator")}</small>}</div></div>
        {setup ? <form onSubmit={confirmTwoFactor} className="mt-4 rounded-2xl border border-[#4a554c] bg-[#292f2a] p-5">
          <div className="flex items-start justify-between gap-3"><div><h3 className="font-semibold">{setup.purpose === "disable" ? t("twoFactor.confirmDisable") : t("twoFactor.finish")}</h3><p className="mt-1 text-sm text-[#99a29b]">{setup.method === "email" ? `${t("twoFactor.emailSent")} ${setup.masked_email || twoFactor.masked_email}` : t("twoFactor.scanHelp")}</p></div><button type="button" aria-label={t("common.close")} onClick={() => setSetup(null)} className="grid h-9 w-9 place-items-center rounded-lg hover:bg-[#394039]"><X size={18}/></button></div>
          {setup.purpose === "setup" && setup.method === "authenticator" && <div className="mt-5 grid gap-5 sm:grid-cols-[180px_1fr] sm:items-center"><img src={setup.qr_code_data_url} alt={t("twoFactor.qrAlt")} className="h-44 w-44 rounded-xl bg-white p-2"/><div><p className="text-sm text-[#adb6af]">{t("twoFactor.manualKey")}</p><code className="mt-2 block break-all rounded-xl bg-[#1b1e1c] p-3 text-sm tracking-wider text-[#b9dfa9]">{setup.secret}</code><p className="mt-3 text-xs text-[#7f8981]">{t("twoFactor.supportedApps")}</p></div></div>}
          <div className="mt-5 flex flex-col gap-3 sm:flex-row"><input name="code" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" maxLength={6} required autoFocus placeholder="000000" aria-label={t("twoFactor.code")} className="min-h-12 flex-1 rounded-xl border border-[#566158] bg-[#1b1e1c] px-4 text-center text-xl font-bold tracking-[.35em] outline-none focus:border-[#73b979]"/><button disabled={twoFactorBusy} className="flex min-h-12 items-center justify-center gap-2 rounded-xl bg-[#438a56] px-5 font-semibold disabled:opacity-50">{twoFactorBusy ? <LoaderCircle className="animate-spin" size={17}/> : <KeyRound size={17}/>} {setup.purpose === "disable" ? t("twoFactor.disable") : t("twoFactor.verifyEnable")}</button></div>
        </form> : <div className="mt-4">
          <label className="block max-w-md text-sm text-[#bbc3bd]">{t("settings.currentPassword")}<input value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} type="password" autoComplete="current-password" className="mt-2 w-full rounded-xl border border-[#4a534c] bg-[#1b1e1c] p-3.5 text-white outline-none focus:border-[#73b979]"/></label>
          {twoFactor.enabled ? <button onClick={() => void beginDisable()} disabled={twoFactorBusy} className="mt-4 flex min-h-11 items-center gap-2 rounded-xl border border-[#84524b] px-5 font-semibold text-[#e7aaa0] hover:bg-[#3d2926] disabled:opacity-50"><LockKeyhole size={17}/>{t("twoFactor.disable")}</button> : <div className="mt-4 grid gap-3 sm:grid-cols-2"><MethodButton icon={<Smartphone/>} title={t("twoFactor.authenticator")} help={t("twoFactor.authenticatorHelp")} disabled={twoFactorBusy} onClick={() => void beginTwoFactor("authenticator")}/><MethodButton icon={<Mail/>} title={t("twoFactor.email")} help={twoFactor.email_configured ? `${t("twoFactor.emailHelp")} ${twoFactor.masked_email}` : t("twoFactor.emailUnavailable")} disabled={twoFactorBusy || !twoFactor.email_configured} onClick={() => void beginTwoFactor("email")}/></div>}
        </div>}
      </div>}
    </section>

    <section className="rounded-3xl border border-[#3a423c] bg-[#222623] p-5 sm:p-7"><SectionTitle icon={<BellRing/>} title={t("notifications.title")} help={t("notifications.subtitle")}/>{loading ? <LoaderCircle className="mt-6 animate-spin text-[#86c67e]"/> : preferences && <><div className={`mt-5 flex items-center gap-3 rounded-2xl border p-4 ${preferences.email_configured ? "border-[#49664d] bg-[#27372a] text-[#b9dfad]" : "border-[#735d39] bg-[#382f22] text-[#e3c38b]"}`}><MailCheck size={20}/><strong className="text-sm">{preferences.email_configured ? t("notifications.ready") : t("notifications.notReady")}</strong></div><Toggle label={t("notifications.master")} checked={preferences.enabled} onChange={(value) => void updatePreference("enabled", value)} prominent/><div className="mt-3 grid gap-x-6 rounded-2xl border border-[#3b433d] bg-[#252a26] px-4 sm:grid-cols-2">{categories.map(([key, label]) => <Toggle key={key} label={t(label)} checked={Boolean(preferences[key])} disabled={!preferences.enabled} onChange={(value) => void updatePreference(key, value)}/>)}</div></>}</section>
    <section className="rounded-3xl border border-[#3a423c] bg-[#222623] p-5 sm:p-7"><SectionTitle icon={<LockKeyhole/>} title={t("settings.security")} help={t("settings.securityHelp")}/><form onSubmit={changePassword} className="mt-5 grid gap-4 sm:grid-cols-3"><Password name="current_password" label={t("settings.currentPassword")}/><Password name="new_password" label={t("settings.newPassword")}/><Password name="confirm_password" label={t("settings.confirmPassword")}/><div className="sm:col-span-3"><button disabled={passwordBusy} className="flex h-11 items-center gap-2 rounded-xl bg-[#438a56] px-5 font-semibold hover:bg-[#4d9d62] disabled:opacity-50">{passwordBusy ? <LoaderCircle className="animate-spin" size={17}/> : <ShieldCheck size={17}/>} {t("settings.changePassword")}</button></div></form></section>
    {message && <p className="flex items-center gap-2 rounded-xl bg-[#29402d] p-3 text-sm text-[#b9dcae]"><CheckCircle2 size={17}/>{message}</p>}{error && <p role="alert" className="rounded-xl bg-[#442a26] p-3 text-sm text-[#ebb4a8]">{error}</p>}
  </div>;
}

function SectionTitle({ icon, title, help }: { icon: React.ReactNode; title: string; help: string }) { return <div className="flex items-start gap-3"><span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-[#304333] text-[#91d08b]">{icon}</span><div><h2 className="text-lg font-semibold sm:text-xl">{title}</h2><p className="mobile-secondary mt-1 text-sm text-[#929c94]">{help}</p></div></div>; }
function MethodButton({ icon, title, help, disabled, onClick }: { icon: React.ReactNode; title: string; help: string; disabled: boolean; onClick: () => void }) { return <button onClick={onClick} disabled={disabled} className="flex min-h-28 items-start gap-4 rounded-2xl border border-[#424b44] bg-[#292e2a] p-5 text-left hover:border-[#628168] hover:bg-[#303732] disabled:cursor-not-allowed disabled:opacity-40"><span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-[#304333] text-[#91d08b]">{icon}</span><span><strong className="block">{title}</strong><small className="mt-2 block leading-5 text-[#929c94]">{help}</small></span></button>; }
function Toggle({ label, checked, disabled = false, prominent = false, onChange }: { label: string; checked: boolean; disabled?: boolean; prominent?: boolean; onChange: (value: boolean) => void }) { return <div className={`flex min-h-14 items-center justify-between gap-4 ${prominent ? "mt-4 rounded-2xl border border-[#3f4941] bg-[#252b27] px-4" : "border-b border-[#343a36] py-3 last:border-0"}`}><span className={`text-sm ${disabled ? "text-[#697169]" : "text-[#d7ddd8]"}`}>{label}</span><button type="button" role="switch" aria-checked={checked} disabled={disabled} onClick={() => onChange(!checked)} className={`relative h-7 w-12 shrink-0 rounded-full transition ${checked ? "bg-[#5ea767]" : "bg-[#4a504b]"} disabled:opacity-40`}><span className={`absolute top-1 h-5 w-5 rounded-full bg-white shadow transition ${checked ? "left-6" : "left-1"}`}/></button></div>; }
function Password({ name, label }: { name: string; label: string }) { return <label className="text-sm text-[#bbc3bd]">{label}<input name={name} type="password" minLength={name === "current_password" ? 1 : 8} required autoComplete={name === "current_password" ? "current-password" : "new-password"} className="mt-2 w-full rounded-xl border border-[#4a534c] bg-[#1b1e1c] p-3.5 text-white outline-none focus:border-[#73b979]"/></label>; }
