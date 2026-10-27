"use client";

import Image from "next/image";
import { FormEvent, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  Eye,
  EyeOff,
  KeyRound,
  Leaf,
  LockKeyhole,
  Mail,
  ShieldCheck,
  UserRound,
} from "lucide-react";

import { api } from "@/lib/api";
import { copy, Language, message } from "@/lib/i18n";
import BrandLogo from "./BrandLogo";

type Challenge = {
  challenge_token: string;
  method: "email" | "authenticator";
  purpose: "login" | "registration";
  masked_email?: string | null;
};

type AuthResponse = {
  access_token?: string;
  two_factor_required?: boolean;
  email_verification_required?: boolean;
  challenge_token?: string;
  method?: "email" | "authenticator";
  masked_email?: string | null;
};

const inputClass =
  "auth-input min-h-13 w-full rounded-2xl border border-[#cbd5c9] bg-white px-11 py-3.5 text-[#162219] outline-none transition placeholder:text-[#869087] focus:border-[#4f8a58] focus:ring-4 focus:ring-[#6eaa741c]";

export default function AuthPanel({
  language,
  onAuth,
}: {
  language: Language;
  onAuth: (token: string) => void;
}) {
  const t = copy[language];
  const m = (key: string) => message(language, key);
  const [mode, setMode] = useState<"login" | "register">("login");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [challenge, setChallenge] = useState<Challenge | null>(null);

  function finishAuth(token: string) {
    localStorage.setItem("agrinox_token", token);
    onAuth(token);
  }

  function changeMode(next: "login" | "register") {
    setMode(next);
    setChallenge(null);
    setError("");
    setShowPassword(false);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const values = Object.fromEntries(new FormData(event.currentTarget));
    if (mode === "register" && values.password !== values.confirm_password) {
      setError(m("auth.passwordMismatch"));
      return;
    }
    delete values.confirm_password;
    setBusy(true);
    setError("");
    try {
      const result = await api<AuthResponse>(`/auth/${mode}`, {
        method: "POST",
        body: JSON.stringify(values),
      });
      if (result.challenge_token && result.method) {
        setChallenge({
          challenge_token: result.challenge_token,
          method: result.method,
          purpose: result.email_verification_required ? "registration" : "login",
          masked_email: result.masked_email,
        });
        return;
      }
      if (!result.access_token) throw new Error(m("auth.couldNotComplete"));
      finishAuth(result.access_token);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : m("auth.couldNotComplete"));
    } finally {
      setBusy(false);
    }
  }

  async function verifyCode(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!challenge) return;
    setBusy(true);
    setError("");
    const code = String(new FormData(event.currentTarget).get("code") || "");
    try {
      const endpoint = challenge.purpose === "registration" ? "/auth/register/verify" : "/auth/2fa/login/verify";
      const result = await api<{ access_token: string }>(endpoint, {
        method: "POST",
        body: JSON.stringify({ challenge_token: challenge.challenge_token, code }),
      });
      finishAuth(result.access_token);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : m("auth.unableVerify"));
    } finally {
      setBusy(false);
    }
  }

  const registrationChallenge = challenge?.purpose === "registration";

  return (
    <main className="auth-page relative min-h-screen overflow-hidden bg-[#eef3ea] text-[#172219] lg:grid lg:grid-cols-[minmax(0,1.08fr)_minmax(430px,.92fr)]">
      <div
        aria-hidden="true"
        className="auth-imigongo-strip pointer-events-none absolute inset-y-0 right-0 z-30 w-6 sm:w-8"
      />

      <section className="relative mr-6 min-h-[310px] overflow-hidden sm:mr-8 lg:mr-0 lg:min-h-screen">
        <Image
          src="/auth-irrigation-wallpaper.jpg"
          alt="Irrigated farmland in Rwanda"
          fill
          priority
          sizes="(max-width: 1024px) 100vw, 58vw"
          className="object-cover object-center"
        />
        <div className="absolute inset-0 bg-[linear-gradient(180deg,rgba(8,28,17,.16),rgba(8,28,17,.32)_44%,rgba(7,23,14,.88))]" />
        <div className="absolute inset-0 bg-[linear-gradient(90deg,rgba(12,43,25,.1),transparent_55%)]" />

        <div className="relative flex h-full min-h-[310px] flex-col justify-between p-6 text-white sm:p-10 lg:min-h-screen lg:p-14 xl:p-16">
          <BrandLogo className="text-white" markClassName="h-11 w-11 drop-shadow-lg"/>

          <div className="max-w-2xl pb-1 lg:pb-8">
            <p className="mb-4 flex items-center gap-2 text-xs font-bold uppercase tracking-[.2em] text-[#c8ef9b]">
              <Leaf size={16} /> {m("auth.farmerWorkspace")}
            </p>
            <h1 className="max-w-xl text-3xl font-semibold leading-tight sm:text-4xl lg:text-5xl xl:text-[3.5rem]">
              {m("auth.heroTitle")}
            </h1>
            <p className="mt-4 max-w-xl text-sm leading-6 text-white/80 sm:text-base sm:leading-7">
              {m("auth.heroHelp")}
            </p>
            <div className="mt-7 hidden flex-wrap gap-3 sm:flex">
              {[m("auth.featureFarm"), m("auth.featureWeather"), m("auth.featureAdvice")].map((item) => (
                <span key={item} className="flex items-center gap-2 rounded-full border border-white/25 bg-black/20 px-3 py-2 text-xs font-semibold backdrop-blur-sm">
                  <CheckCircle2 size={15} className="text-[#bce88a]" /> {item}
                </span>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="auth-form-panel relative mr-6 flex min-h-[calc(100vh-310px)] items-center justify-center bg-[#f4f7f1] px-5 py-10 sm:mr-8 sm:px-10 lg:min-h-screen lg:px-12 xl:px-20">
        <div className="w-full max-w-[500px]">
          {!challenge && (
            <div className="auth-tabs mb-8 grid grid-cols-2 rounded-2xl border border-[#d3dbd1] bg-[#e7ede4] p-1.5" role="tablist" aria-label={m("auth.accountAccess")}>
              <button type="button" role="tab" aria-selected={mode === "login"} onClick={() => changeMode("login")} className={`min-h-11 rounded-xl px-4 text-sm font-bold transition ${mode === "login" ? "auth-tab-active bg-white text-[#17341e] shadow-sm" : "auth-tab-inactive text-[#627066] hover:text-[#263c2b]"}`}>
                {t.signIn}
              </button>
              <button type="button" role="tab" aria-selected={mode === "register"} onClick={() => changeMode("register")} className={`min-h-11 rounded-xl px-4 text-sm font-bold transition ${mode === "register" ? "auth-tab-active bg-white text-[#17341e] shadow-sm" : "auth-tab-inactive text-[#627066] hover:text-[#263c2b]"}`}>
                {t.register}
              </button>
            </div>
          )}

          <p className="auth-eyebrow text-xs font-bold uppercase tracking-[.18em] text-[#4d8b57]">
            {challenge ? (registrationChallenge ? m("auth.confirmAccount") : m("auth.twoFactor")) : mode === "login" ? t.welcome : t.account}
          </p>
          <h2 className="auth-title mt-2 text-3xl font-semibold tracking-tight text-[#172219] sm:text-4xl">
            {challenge ? m("auth.enterCode") : mode === "login" ? t.signIn : t.register}
          </h2>
          <p className="auth-copy mt-3 max-w-md text-sm leading-6 text-[#68746b]">
            {challenge
              ? challenge.method === "email"
                ? `${m("auth.codeSent")} ${challenge.masked_email || m("auth.yourEmail")}.`
                : m("auth.openAuthenticator")
              : mode === "login"
                ? m("auth.signInHelp")
                : m("auth.registerHelp")}
          </p>

          {challenge ? (
            <form onSubmit={verifyCode} className="mt-7 space-y-4">
              <div className="auth-challenge flex items-start gap-3 rounded-2xl border border-[#bdd0bd] bg-[#e7f0e4] p-4 text-[#2d5734]">
                <span className="mt-0.5 grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-white">
                  {challenge.method === "email" ? <Mail size={19} /> : <KeyRound size={19} />}
                </span>
                <div>
                  <strong className="block text-sm">{registrationChallenge ? m("auth.emailConfirmation") : challenge.method === "email" ? m("auth.emailVerification") : m("twoFactor.authenticator")}</strong>
                  <span className="mt-1 block text-xs leading-5 text-[#637865]">{registrationChallenge ? m("auth.confirmBeforeUse") : m("auth.secondStepHelp")}</span>
                </div>
              </div>
              <label className="block text-sm font-semibold text-[#344138]">
                {m("auth.sixDigitCode")}
                <input name="code" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" maxLength={6} required autoFocus placeholder="000000" className="auth-input mt-2 min-h-15 w-full rounded-2xl border border-[#b9c7b9] bg-white px-4 text-center text-3xl font-bold tracking-[.42em] text-[#18321f] outline-none focus:border-[#4f8a58] focus:ring-4 focus:ring-[#6eaa7420]" />
              </label>
              {error && <p role="alert" className="rounded-xl border border-[#e0aaa3] bg-[#fff0ed] p-3 text-sm text-[#9d3328]">{error}</p>}
              <button disabled={busy} className="flex min-h-13 w-full items-center justify-center gap-2 rounded-2xl bg-[#2f7245] px-5 font-bold text-white shadow-lg shadow-[#245c3730] transition hover:bg-[#285f3b] disabled:cursor-not-allowed disabled:opacity-55">
                <ShieldCheck size={19} /> {busy ? m("auth.verifying") : registrationChallenge ? m("auth.verifyCreate") : m("auth.verifySignIn")}
              </button>
              <button type="button" onClick={() => { setChallenge(null); setError(""); }} className="flex min-h-11 w-full items-center justify-center gap-2 text-sm font-semibold text-[#667168] hover:text-[#244c2d]">
                <ArrowLeft size={16} /> {registrationChallenge ? m("auth.backRegister") : m("auth.backSignIn")}
              </button>
            </form>
          ) : (
            <form onSubmit={submit} className="mt-7 space-y-4">
              {mode === "register" && (
                <label className="block text-sm font-semibold text-[#344138]">
                  {m("auth.fullName")}
                  <span className="relative mt-2 block">
                    <UserRound className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-[#718077]" size={18} />
                    <input name="full_name" required minLength={2} autoComplete="name" placeholder={m("auth.namePlaceholder")} className={inputClass} />
                  </span>
                </label>
              )}
              <label className="block text-sm font-semibold text-[#344138]">
                {m("auth.email")}
                <span className="relative mt-2 block">
                  <Mail className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-[#718077]" size={18} />
                  <input name="email" type="email" required autoComplete="email" placeholder="name@example.com" className={inputClass} />
                </span>
              </label>
              <label className="block text-sm font-semibold text-[#344138]">
                {m("auth.password")}
                <span className="relative mt-2 block">
                  <LockKeyhole className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-[#718077]" size={18} />
                  <input name="password" type={showPassword ? "text" : "password"} minLength={8} required autoComplete={mode === "login" ? "current-password" : "new-password"} placeholder={m("auth.passwordPlaceholder")} className={`${inputClass} pr-12`} />
                  <button type="button" onClick={() => setShowPassword((current) => !current)} className="absolute right-2 top-1/2 grid h-10 w-10 -translate-y-1/2 place-items-center rounded-xl text-[#647168] hover:bg-[#eef3ec]" aria-label={showPassword ? m("auth.hidePassword") : m("auth.showPassword")}>
                    {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </span>
              </label>
              {mode === "register" && (
                <>
                  <label className="block text-sm font-semibold text-[#344138]">
                    {m("auth.confirmPassword")}
                    <span className="relative mt-2 block">
                      <ShieldCheck className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-[#718077]" size={18} />
                      <input name="confirm_password" type={showPassword ? "text" : "password"} minLength={8} required autoComplete="new-password" placeholder={m("auth.confirmPasswordPlaceholder")} className={inputClass} />
                    </span>
                  </label>
                  <input type="hidden" name="preferred_language" value={language} />
                  <div className="auth-note flex items-start gap-2 rounded-xl bg-[#e8efe5] p-3 text-xs leading-5 text-[#536357]">
                    <Mail size={16} className="mt-0.5 shrink-0 text-[#4d8b57]" /> {m("auth.registrationEmailNotice")}
                  </div>
                </>
              )}
              {error && <p role="alert" className="rounded-xl border border-[#e0aaa3] bg-[#fff0ed] p-3 text-sm text-[#9d3328]">{error}</p>}
              <button disabled={busy} className="flex min-h-13 w-full items-center justify-center gap-2 rounded-2xl bg-[#2f7245] px-5 font-bold text-white shadow-lg shadow-[#245c3730] transition hover:bg-[#285f3b] disabled:cursor-not-allowed disabled:opacity-55">
                {busy ? m("common.loading") : mode === "login" ? t.signIn : t.register} {!busy && <ArrowRight size={18} />}
              </button>
            </form>
          )}

          <div className="auth-security mt-7 flex items-center justify-center gap-2 text-center text-xs leading-5 text-[#768078]">
            <ShieldCheck size={15} className="shrink-0 text-[#4d8b57]" /> {m("auth.securityNote")}
          </div>
        </div>
      </section>
    </main>
  );
}
