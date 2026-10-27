"use client";

import { useEffect, useRef, useState } from "react";
import { Bell, BellRing, CheckCheck, ChevronRight, LoaderCircle } from "lucide-react";

import { api } from "@/lib/api";
import { useI18n } from "./I18nProvider";

export type AppNotification = {
  id: number;
  category: string;
  title: string;
  message: string;
  is_read: boolean;
  created_at: string;
  read_at?: string | null;
};

export default function NotificationCenter({ token, onViewAll }: { token: string; onViewAll: () => void }) {
  const { t, locale } = useI18n();
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<AppNotification[]>([]);
  const [unread, setUnread] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const root = useRef<HTMLDivElement>(null);

  async function refresh(showLoader = false) {
    if (showLoader) setLoading(true);
    try {
      const [nextItems, count] = await Promise.all([
        api<AppNotification[]>("/notifications?limit=6", {}, token),
        api<{ unread: number }>("/notifications/unread-count", {}, token),
      ]);
      setItems(nextItems);
      setUnread(count.unread);
      setError("");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : t("notificationCenter.loadError"));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 30000);
    const onFocus = () => void refresh();
    const onChanged = () => void refresh();
    window.addEventListener("focus", onFocus);
    window.addEventListener("agrinox-notifications-changed", onChanged);
    return () => { window.clearInterval(timer); window.removeEventListener("focus", onFocus); window.removeEventListener("agrinox-notifications-changed", onChanged); };
  }, [token]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!open) return;
    void refresh(true);
    const close = (event: MouseEvent) => {
      if (root.current && !root.current.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  async function markRead(item: AppNotification) {
    if (item.is_read) return;
    setItems((current) => current.map((entry) => entry.id === item.id ? { ...entry, is_read: true } : entry));
    setUnread((count) => Math.max(0, count - 1));
    try { await api(`/notifications/${item.id}/read`, { method: "PATCH" }, token); }
    catch { void refresh(); }
  }

  async function markAll() {
    setItems((current) => current.map((item) => ({ ...item, is_read: true })));
    setUnread(0);
    try { await api("/notifications/read-all", { method: "POST" }, token); }
    catch { void refresh(); }
  }

  return <div ref={root} className="relative">
    <button onClick={() => setOpen((value) => !value)} aria-label={t("notificationCenter.title")} aria-expanded={open} className={`relative grid h-9 w-9 place-items-center rounded-full border transition ${open ? "border-[#72ad75] bg-[#304333] text-[#b7dfaf]" : "border-[#454945] hover:bg-[#292c2a]"}`}>
      <Bell size={18}/>
      {unread > 0 && <span className="absolute -right-1 -top-1 grid min-h-[18px] min-w-[18px] place-items-center rounded-full border-2 border-[#1d1f1e] bg-[#d86b52] px-1 text-[10px] font-bold leading-none text-white">{unread > 99 ? "99+" : unread}</span>}
    </button>
    {open && <section className="fixed inset-x-3 top-[68px] z-[2100] overflow-hidden rounded-2xl border border-[#404841] bg-[#222623] shadow-2xl sm:absolute sm:inset-x-auto sm:right-0 sm:top-12 sm:w-[390px]" aria-label={t("notificationCenter.recent")}>
      <header className="flex items-start justify-between gap-3 border-b border-[#39403b] p-4">
        <div><h2 className="font-semibold text-white">{t("notificationCenter.title")}</h2><p className="mt-1 text-xs text-[#9ca59e]">{unread ? `${unread} ${t("notificationCenter.unread")}` : t("notificationCenter.caughtUp")}</p></div>
        {unread > 0 && <button onClick={() => void markAll()} className="flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-xs font-semibold text-[#9ed398] hover:bg-[#303a32]"><CheckCheck size={15}/>{t("notificationCenter.markAll")}</button>}
      </header>
      <div className="max-h-[430px] overflow-y-auto">
        {loading && items.length === 0 ? <div className="grid min-h-48 place-items-center"><LoaderCircle className="animate-spin text-[#88c783]"/></div>
          : error && items.length === 0 ? <p role="alert" className="m-4 rounded-xl bg-[#422b27] p-3 text-sm text-[#efb5a8]">{error}</p>
          : items.length === 0 ? <div className="grid min-h-52 place-items-center px-8 text-center"><div><BellRing className="mx-auto text-[#647068]"/><p className="mt-3 font-medium">{t("notificationCenter.empty")}</p><p className="mt-1 text-sm text-[#8e9890]">{t("notificationCenter.emptyHelp")}</p></div></div>
          : items.map((item) => <button key={item.id} onClick={() => void markRead(item)} className={`flex w-full gap-3 border-b border-[#353b37] p-4 text-left transition hover:bg-[#2a302b] ${item.is_read ? "opacity-70" : "bg-[#263029]"}`}>
              <span className={`mt-1 h-2.5 w-2.5 shrink-0 rounded-full ${item.is_read ? "bg-[#56605a]" : "bg-[#79c878]"}`}/>
              <span className="min-w-0 flex-1"><strong className="block truncate text-sm text-white">{item.title}</strong><span className="mt-1 line-clamp-2 block whitespace-pre-line text-xs leading-5 text-[#aeb6b0]">{item.message}</span><time className="mt-2 block text-[11px] text-[#7f8982]">{new Date(item.created_at).toLocaleString(locale, { dateStyle: "medium", timeStyle: "short" })}</time></span>
            </button>)}
      </div>
      <button onClick={() => { setOpen(false); onViewAll(); }} className="flex min-h-12 w-full items-center justify-center gap-2 bg-[#292f2b] text-sm font-semibold text-[#a9d9a4] hover:bg-[#303832]">{t("notificationCenter.viewAll")}<ChevronRight size={16}/></button>
    </section>}
  </div>;
}
