"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import {
  AtSign, BadgeCheck, Camera, Check, CheckCircle2, ImagePlus, Languages, Leaf,
  LoaderCircle, Mail, MapPin, MapPinned, PencilLine, Phone, ShieldCheck,
  Sprout, Trash2, UserRound,
} from "lucide-react";

import { api, apiForm, type CurrentUser, type Farm } from "@/lib/api";
import { useI18n } from "./I18nProvider";
import UserAvatar, { AvatarPortrait, avatarColors, avatarOptions, type AvatarColor, type AvatarKey } from "./UserAvatar";

type TwoFactorStatus = { enabled: boolean; method: "email" | "authenticator" | null };

export default function ProfilePage({ token, user, farms, onUpdated }: { token: string; user: CurrentUser | null; farms: Farm[]; onUpdated: (user: CurrentUser) => void }) {
  const { t, locale } = useI18n();
  const [editing, setEditing] = useState(false);
  const [choosingAvatar, setChoosingAvatar] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [security, setSecurity] = useState<TwoFactorStatus | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const fields = useMemo(() => farms.reduce((sum, farm) => sum + farm.fields.length, 0), [farms]);
  const landHa = useMemo(() => farms.reduce((sum, farm) => sum + farm.fields.reduce((fieldSum, field) => fieldSum + field.area_m2, 0), 0) / 10_000, [farms]);
  const completion = useMemo(() => {
    if (!user) return 0;
    const values = [user.full_name, user.email, user.phone, user.location, user.bio, farms.length > 0];
    return Math.round((values.filter(Boolean).length / values.length) * 100);
  }, [user, farms.length]);

  useEffect(() => { setEditing(false); setChoosingAvatar(false); setError(""); }, [user?.id]);
  useEffect(() => {
    let active = true;
    api<TwoFactorStatus>("/auth/2fa/status", {}, token).then((value) => { if (active) setSecurity(value); }).catch(() => undefined);
    return () => { active = false; };
  }, [token]);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(""); setSaved(false);
    const values = Object.fromEntries(new FormData(event.currentTarget));
    try {
      const next = await api<CurrentUser>("/auth/me", { method: "PATCH", body: JSON.stringify({
        full_name: values.full_name, email: values.email, phone: values.phone || null,
        location: values.location || null, bio: values.bio || null,
      }) }, token);
      onUpdated(next); setEditing(false); setSaved(true);
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : t("common.error")); }
    finally { setBusy(false); }
  }

  async function chooseVector(avatar_key: AvatarKey, avatar_color: AvatarColor = user?.avatar_color || "forest") {
    setBusy(true); setError("");
    try {
      const next = await api<CurrentUser>("/auth/me", { method: "PATCH", body: JSON.stringify({ avatar_key, avatar_color }) }, token);
      onUpdated(next); setSaved(true);
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : t("common.error")); }
    finally { setBusy(false); }
  }

  async function uploadPhoto(file: File) {
    setBusy(true); setError("");
    try {
      const form = new FormData(); form.append("image", file);
      const next = await apiForm<CurrentUser>("/auth/me/avatar", form, token);
      onUpdated(next); setSaved(true); setChoosingAvatar(false);
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : t("common.error")); }
    finally { setBusy(false); if (fileRef.current) fileRef.current.value = ""; }
  }

  async function removePhoto() {
    setBusy(true); setError("");
    try {
      const next = await api<CurrentUser>("/auth/me/avatar", { method: "DELETE" }, token);
      onUpdated(next); setSaved(true);
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : t("common.error")); }
    finally { setBusy(false); }
  }

  if (!user) return <div className="grid min-h-[55vh] place-items-center"><LoaderCircle className="animate-spin text-[#82c979]" size={28}/></div>;

  return <div className="space-y-5 pb-8">
    <section className="profile-hero theme-on-dark relative overflow-hidden rounded-[2rem] border border-[#3b5141] bg-[linear-gradient(120deg,#16271d_0%,#254a31_57%,#426d3e_100%)] px-5 pb-6 pt-7 sm:px-8 sm:pb-8">
      <div aria-hidden className="absolute inset-0 opacity-30 [background-image:radial-gradient(circle_at_78%_25%,rgba(191,232,127,.5),transparent_25%),linear-gradient(135deg,transparent_44%,rgba(255,255,255,.07)_45%,transparent_46%)]"/>
      <div className="relative flex flex-col gap-6 lg:flex-row lg:items-end">
        <div className="relative shrink-0">
          <UserAvatar user={user} token={token} size="large" className="border-4 shadow-2xl"/>
          <button type="button" onClick={() => setChoosingAvatar((value) => !value)} aria-label={t("profile.changePhoto")} className="absolute -bottom-1 -right-1 grid h-11 w-11 place-items-center rounded-2xl border-4 border-[#203d29] bg-[#f1f6eb] text-[#23432e] shadow-lg hover:scale-105"><Camera size={19}/></button>
        </div>
        <div className="min-w-0 flex-1">
          <div className="mb-2 flex flex-wrap items-center gap-2"><span className="rounded-full bg-white/10 px-3 py-1 text-xs font-bold uppercase tracking-[.15em] text-[#c5eba8]">{t("profile.account")}</span><span className="flex items-center gap-1 rounded-full bg-[#9cd574] px-2.5 py-1 text-xs font-bold text-[#17351f]"><BadgeCheck size={14}/>{t("profile.verified")}</span></div>
          <h1 className="truncate text-3xl font-bold sm:text-4xl">{user.full_name}</h1>
          <p className="mt-2 flex items-center gap-2 text-sm text-[#d6e3d7]"><AtSign size={15}/>{user.email}</p>
          {user.location && <p className="mt-1.5 flex items-center gap-2 text-sm text-[#d6e3d7]"><MapPin size={15}/>{user.location}</p>}
        </div>
        <button onClick={() => { setEditing((value) => !value); setSaved(false); }} className="flex h-11 items-center justify-center gap-2 rounded-xl border border-white/30 bg-black/10 px-5 text-sm font-semibold hover:bg-white/10"><PencilLine size={17}/>{editing ? t("common.cancel") : t("profile.edit")}</button>
      </div>
      <div className="relative mt-6 max-w-xl">
        <div className="flex items-center justify-between text-xs font-semibold"><span>{t("profile.completion")}</span><span>{completion}%</span></div>
        <div className="mt-2 h-2 overflow-hidden rounded-full bg-black/25"><div className="h-full rounded-full bg-[#a7d977] transition-all" style={{ width: `${completion}%` }}/></div>
      </div>
    </section>

    {choosingAvatar && <section className="profile-card rounded-3xl border border-[#3a413c] bg-[#222623] p-5 sm:p-7">
      <div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="text-xl font-semibold">{t("profile.chooseAvatar")}</h2><p className="mt-1 text-sm text-[#939d95]">{t("profile.avatarHelp")}</p></div><button onClick={() => fileRef.current?.click()} disabled={busy} className="flex h-11 items-center gap-2 rounded-xl bg-[#438a56] px-4 text-sm font-semibold text-white"><ImagePlus size={18}/>{t("profile.uploadPhoto")}</button></div>
      <input ref={fileRef} type="file" accept="image/jpeg,image/png,image/webp" className="hidden" onChange={(event) => { const file = event.target.files?.[0]; if (file) void uploadPhoto(file); }}/>
      <div className="mt-5 grid grid-cols-3 gap-3 sm:grid-cols-6">{avatarOptions.map(({ key, label }) => <button key={key} onClick={() => void chooseVector(key)} disabled={busy} aria-label={label} aria-pressed={user.avatar_kind === "vector" && user.avatar_key === key} className={`relative aspect-square overflow-hidden rounded-2xl border bg-gradient-to-br ${avatarColors[user.avatar_color]} text-white transition hover:-translate-y-1 disabled:opacity-50 ${user.avatar_kind === "vector" && user.avatar_key === key ? "border-[#a9df82] ring-2 ring-[#79b96c]" : "border-[#4a534c]"}`}><AvatarPortrait variant={key}/>{user.avatar_kind === "vector" && user.avatar_key === key && <span className="absolute right-1.5 top-1.5 grid h-6 w-6 place-items-center rounded-full bg-[#17351f] text-[#c8efa9] shadow"><Check size={14}/></span>}</button>)}</div>
      <div className="mt-5 flex flex-wrap items-center gap-3"><span className="text-sm text-[#aeb7b0]">{t("profile.color")}</span>{(Object.keys(avatarColors) as AvatarColor[]).map((color) => <button key={color} onClick={() => void chooseVector(user.avatar_key, color)} aria-label={color} className={`h-9 w-9 rounded-full border-2 bg-gradient-to-br ${avatarColors[color]} ${user.avatar_color === color ? "border-white ring-2 ring-[#72b96c]" : "border-transparent"}`}/>)}</div>
      {user.has_profile_photo && <button onClick={() => void removePhoto()} disabled={busy} className="mt-5 flex items-center gap-2 text-sm font-semibold text-[#efaa9d]"><Trash2 size={16}/>{t("profile.removePhoto")}</button>}
      <p className="mt-4 text-xs text-[#7f8981]">{t("profile.photoRules")}</p>
    </section>}

    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <Stat icon={<MapPinned size={20}/>} value={farms.length} label={t("profile.farms")}/>
      <Stat icon={<Sprout size={20}/>} value={fields} label={t("profile.fields")}/>
      <Stat icon={<Leaf size={20}/>} value={`${landHa.toLocaleString(locale, { maximumFractionDigits: 2 })} ha`} label={t("profile.landManaged")}/>
      <Stat icon={<UserRound size={20}/>} value={new Date(user.created_at).toLocaleDateString(locale, { year: "numeric", month: "short" })} label={t("profile.memberSince")}/>
    </div>

    <div className="grid gap-5 xl:grid-cols-[1.45fr_.75fr]">
      <section className="profile-card rounded-3xl border border-[#3a413c] bg-[#222623] p-5 sm:p-7">
        <div><h2 className="text-xl font-semibold">{t("profile.personal")}</h2><p className="mt-1 text-sm text-[#939d95]">{t("profile.personalHelp")}</p></div>
        {editing ? <form onSubmit={save} className="mt-6 grid gap-5 sm:grid-cols-2">
          <Field label={t("auth.fullName")} name="full_name" defaultValue={user.full_name} required/>
          <Field label={t("auth.email")} name="email" type="email" defaultValue={user.email} required/>
          <Field label={t("profile.phone")} name="phone" type="tel" defaultValue={user.phone || ""} placeholder="+250 7…"/>
          <Field label={t("profile.location")} name="location" defaultValue={user.location || ""} placeholder={t("profile.locationPlaceholder")}/>
          <label className="text-sm text-[#bbc3bd] sm:col-span-2">{t("profile.aboutYou")}<textarea name="bio" defaultValue={user.bio || ""} maxLength={500} rows={4} placeholder={t("profile.bioPlaceholder")} className="mt-2 w-full resize-none rounded-xl border border-[#4a534c] bg-[#1b1e1c] p-3.5 text-white outline-none focus:border-[#73b979]"/></label>
          <div className="flex flex-wrap items-center gap-3 sm:col-span-2"><button disabled={busy} className="flex h-11 items-center gap-2 rounded-xl bg-[#438a56] px-5 font-semibold text-white hover:bg-[#4d9d62] disabled:opacity-50">{busy && <LoaderCircle className="animate-spin" size={17}/>} {t("profile.save")}</button>{error && <p role="alert" className="text-sm text-[#f0afa3]">{error}</p>}</div>
        </form> : <div className="mt-6 grid gap-3 sm:grid-cols-2">
          <Info icon={<UserRound size={17}/>} label={t("auth.fullName")} value={user.full_name}/><Info icon={<Mail size={17}/>} label={t("auth.email")} value={user.email}/>
          <Info icon={<Phone size={17}/>} label={t("profile.phone")} value={user.phone || t("profile.notAdded")}/><Info icon={<MapPin size={17}/>} label={t("profile.location")} value={user.location || t("profile.notAdded")}/>
          <div className="profile-subcard rounded-2xl bg-[#292e2a] p-4 sm:col-span-2"><span className="text-xs uppercase tracking-[.12em] text-[#7f8981]">{t("profile.aboutYou")}</span><p className={`mt-2 text-sm leading-6 ${user.bio ? "text-[#dce2dd]" : "text-[#838c85]"}`}>{user.bio || t("profile.noBio")}</p></div>
        </div>}
        {saved && <p className="mt-4 flex items-center gap-2 rounded-xl bg-[#29402d] p-3 text-sm text-[#b9dcae]"><CheckCircle2 size={17}/>{t("profile.saved")}</p>}
        {!editing && error && <p role="alert" className="mt-4 text-sm text-[#f0afa3]">{error}</p>}
      </section>

      <div className="space-y-5">
        <section className="profile-card rounded-3xl border border-[#3a413c] bg-[#222623] p-5">
          <h2 className="flex items-center gap-2 font-semibold"><ShieldCheck className="text-[#85ca7d]" size={20}/>{t("profile.security")}</h2>
          <div className="profile-subcard mt-4 rounded-2xl bg-[#292e2a] p-4"><span className={`flex items-center gap-2 text-sm font-semibold ${security?.enabled ? "text-[#91d78a]" : "text-[#e4c66d]"}`}><span className="h-2 w-2 rounded-full bg-current"/>{security?.enabled ? t("profile.twoStepOn") : t("profile.twoStepOff")}</span><p className="mt-2 text-xs text-[#939d95]">{security?.enabled ? (security.method === "authenticator" ? t("profile.authenticator") : t("profile.emailCode")) : t("profile.securityHelp")}</p></div>
        </section>
        <section className="profile-card rounded-3xl border border-[#3a413c] bg-[#222623] p-5">
          <h2 className="flex items-center gap-2 font-semibold"><Languages className="text-[#85ca7d]" size={20}/>{t("profile.language")}</h2>
          <p className="mt-4 text-lg font-semibold">{user.preferred_language === "rw" ? t("language.kinyarwanda") : t("language.english")}</p><p className="mt-1 text-xs text-[#939d95]">{t("profile.languageHelp")}</p>
        </section>
      </div>
    </div>
  </div>;
}

function Stat({ icon, value, label }: { icon: React.ReactNode; value: string | number; label: string }) { return <div className="profile-card rounded-2xl border border-[#39423b] bg-[#232824] p-5"><span className="grid h-10 w-10 place-items-center rounded-xl bg-[#304333] text-[#8fd188]">{icon}</span><strong className="mt-4 block text-2xl">{value}</strong><span className="mt-1 block text-sm text-[#939d95]">{label}</span></div>; }
function Info({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) { return <div className="profile-subcard rounded-2xl bg-[#292e2a] p-4"><span className="flex items-center gap-2 text-xs uppercase tracking-[.12em] text-[#7f8981]">{icon}{label}</span><strong className="mt-2 block break-words text-sm font-medium">{value}</strong></div>; }
function Field({ label, name, defaultValue, type = "text", required = false, placeholder }: { label: string; name: string; defaultValue: string; type?: string; required?: boolean; placeholder?: string }) { return <label className="text-sm text-[#bbc3bd]">{label}<input name={name} type={type} defaultValue={defaultValue} required={required} minLength={required ? 2 : undefined} placeholder={placeholder} className="mt-2 w-full rounded-xl border border-[#4a534c] bg-[#1b1e1c] p-3.5 text-white outline-none focus:border-[#73b979]"/></label>; }
