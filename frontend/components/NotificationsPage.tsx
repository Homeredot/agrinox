"use client";

import { useEffect, useMemo, useState } from "react";
import { BellRing, Check, CheckCheck, CircleAlert, Cpu, Droplets, FlaskConical, Leaf, LoaderCircle, RefreshCw, ShieldCheck, Sprout, WalletCards } from "lucide-react";

import { api } from "@/lib/api";
import { useI18n } from "./I18nProvider";
import type { AppNotification } from "./NotificationCenter";

const icons: Record<string, typeof BellRing> = {
  calendar_reminders: CircleAlert,
  irrigation_events: Droplets,
  device_alerts: Cpu,
  soil_alerts: FlaskConical,
  plant_results: Leaf,
  planning_updates: Sprout,
  finance_updates: WalletCards,
  security_updates: ShieldCheck,
};

const categoryKeys: Record<string, string> = {
  calendar_reminders: "notifications.calendar",
  irrigation_events: "notifications.irrigation",
  device_alerts: "notifications.devices",
  soil_alerts: "notifications.soil",
  plant_results: "notifications.plant",
  planning_updates: "notifications.planning",
  finance_updates: "notifications.finance",
  security_updates: "notifications.security",
};

export default function NotificationsPage({ token }: { token: string }) {
  const { t, locale } = useI18n();
  const [items, setItems] = useState<AppNotification[]>([]);
  const [filter, setFilter] = useState<"all" | "unread">("all");
  const [category, setCategory] = useState("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    try {
      setItems(await api<AppNotification[]>("/notifications?limit=100", {}, token));
      setError("");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : t("notificationCenter.loadError"));
    } finally { setLoading(false); }
  }

  useEffect(() => { void load(); }, [token]); // eslint-disable-line react-hooks/exhaustive-deps

  const visible = useMemo(() => items.filter((item) => (filter === "all" || !item.is_read) && (category === "all" || item.category === category)), [items, filter, category]);
  const unread = items.filter((item) => !item.is_read).length;
  const categories = Array.from(new Set(items.map((item) => item.category)));

  async function markRead(id: number) {
    setItems((current) => current.map((item) => item.id === id ? { ...item, is_read: true } : item));
    try { await api(`/notifications/${id}/read`, { method: "PATCH" }, token); window.dispatchEvent(new Event("agrinox-notifications-changed")); }
    catch { void load(); }
  }

  async function markAll() {
    setItems((current) => current.map((item) => ({ ...item, is_read: true })));
    try { await api("/notifications/read-all", { method: "POST" }, token); window.dispatchEvent(new Event("agrinox-notifications-changed")); }
    catch { void load(); }
  }

  return <div className="space-y-6">
    <header className="flex flex-wrap items-end justify-between gap-4">
      <div><p className="mobile-secondary text-xs font-bold uppercase tracking-[.2em] text-[#85c67f]">Agrinox</p><h1 className="text-2xl font-semibold sm:mt-2 sm:text-4xl">{t("notificationCenter.title")}</h1><p className="mobile-secondary mt-2 max-w-2xl text-[#aab2ac]">{t("notificationCenter.subtitle")}</p></div>
      <div className="flex gap-2"><button onClick={() => void load()} disabled={loading} className="grid h-11 w-11 place-items-center rounded-xl border border-[#424a44] hover:bg-[#292f2b]" aria-label={t("notificationCenter.refresh")}><RefreshCw size={18} className={loading ? "animate-spin" : ""}/></button>{unread > 0 && <button onClick={() => void markAll()} className="flex h-11 items-center gap-2 rounded-xl bg-[#39764d] px-4 text-sm font-semibold hover:bg-[#458a5a]"><CheckCheck size={18}/>{t("notificationCenter.markAll")}</button>}</div>
    </header>

    <section className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-[#384039] bg-[#222623] p-3">
      <div className="flex rounded-xl bg-[#1b1e1c] p-1"><button onClick={() => setFilter("all")} className={`rounded-lg px-4 py-2 text-sm font-medium ${filter === "all" ? "bg-[#344137] text-white" : "text-[#9ca59e]"}`}>{t("notificationCenter.all")} <span className="ml-1 text-xs">{items.length}</span></button><button onClick={() => setFilter("unread")} className={`rounded-lg px-4 py-2 text-sm font-medium ${filter === "unread" ? "bg-[#344137] text-white" : "text-[#9ca59e]"}`}>{t("notificationCenter.unread")} <span className="ml-1 text-xs">{unread}</span></button></div>
      <select value={category} onChange={(event) => setCategory(event.target.value)} className="min-h-10 rounded-xl border border-[#454d47] bg-[#292e2a] px-3 text-sm text-white"><option value="all">{t("notificationCenter.allTypes")}</option>{categories.map((value) => <option key={value} value={value}>{t(categoryKeys[value] ?? "", value.replaceAll("_", " "))}</option>)}</select>
    </section>

    {error && <p role="alert" className="rounded-xl border border-[#70453c] bg-[#3d2925] p-4 text-sm text-[#efb5a8]">{error}</p>}
    {loading && items.length === 0 ? <div className="grid min-h-72 place-items-center"><LoaderCircle className="animate-spin text-[#82c27b]"/></div>
      : visible.length === 0 ? <section className="grid min-h-72 place-items-center rounded-3xl border border-dashed border-[#414943] bg-[#202421] p-8 text-center"><div><BellRing className="mx-auto text-[#657168]" size={30}/><h2 className="mt-4 font-semibold">{filter === "unread" ? t("notificationCenter.noUnread") : t("notificationCenter.empty")}</h2><p className="mt-2 text-sm text-[#929c94]">{t("notificationCenter.emptyHelp")}</p></div></section>
      : <section className="overflow-hidden rounded-3xl border border-[#39413b] bg-[#222623]">{visible.map((item) => { const Icon = icons[item.category] ?? BellRing; return <article key={item.id} className={`flex gap-4 border-b border-[#373e39] p-5 last:border-0 sm:p-6 ${item.is_read ? "" : "bg-[#253029]"}`}>
          <span className={`grid h-11 w-11 shrink-0 place-items-center rounded-xl ${item.is_read ? "bg-[#303632] text-[#869088]" : "bg-[#365440] text-[#a8dca5]"}`}><Icon size={20}/></span>
          <div className="min-w-0 flex-1"><div className="flex flex-wrap items-start justify-between gap-2"><div><div className="flex items-center gap-2"><h2 className="font-semibold text-white">{item.title}</h2>{!item.is_read && <span className="rounded-full bg-[#4f8659] px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide">{t("notificationCenter.new")}</span>}</div><p className="mt-1 text-xs text-[#82b985]">{t(categoryKeys[item.category] ?? "", item.category.replaceAll("_", " "))}</p></div><time className="text-xs text-[#879188]">{new Date(item.created_at).toLocaleString(locale, { dateStyle: "medium", timeStyle: "short" })}</time></div><p className="mt-3 whitespace-pre-line text-sm leading-6 text-[#bdc4be]">{item.message}</p></div>
          {!item.is_read && <button onClick={() => void markRead(item.id)} title={t("notificationCenter.markRead")} aria-label={t("notificationCenter.markRead")} className="grid h-9 w-9 shrink-0 place-items-center rounded-lg border border-[#465048] text-[#94c990] hover:bg-[#344137]"><Check size={17}/></button>}
        </article>; })}</section>}
  </div>;
}
