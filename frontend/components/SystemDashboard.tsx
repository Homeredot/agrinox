"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  CalendarDays,
  CheckCircle2,
  CloudSun,
  Cpu,
  FlaskConical,
  LandPlot,
  LoaderCircle,
  MapPinned,
  RefreshCw,
  ScanSearch,
  Satellite,
  Sprout,
  TrendingUp,
  WalletCards,
  Waves,
  Wheat,
  type LucideIcon,
} from "lucide-react";

import { api, type Farm } from "@/lib/api";
import { useI18n } from "./I18nProvider";

type DashboardTarget = "farms" | "weather" | "devices" | "soil" | "planning" | "calendar" | "finance" | "irrigation" | "plant-lens" | "satellite";
type CalendarOverview = { due_today: number; overdue: number; upcoming_7_days: number; completed_this_month: number; total_tasks: number };
type Device = { id: number; field_id: number | null; status: string; is_online?: boolean; sensors: unknown[] };
type CropPlan = { id: number; crop: string; season: string; farm_name: string; field_name: string; planned_planting_date: string };
type FinancePlan = { id: number; planned: { expected_profit_rwf: number }; actual: { actual_profit_rwf: number } };

const EMPTY_CALENDAR: CalendarOverview = { due_today: 0, overdue: 0, upcoming_7_days: 0, completed_this_month: 0, total_tasks: 0 };

function formatRwf(value: number, locale: string) {
  return `${Math.round(value).toLocaleString(locale)} RWF`;
}

export default function SystemDashboard({ farms, token, onOpen }: { farms: Farm[]; token: string; onOpen: (target: DashboardTarget) => void }) {
  const { t, locale } = useI18n();
  const [calendar, setCalendar] = useState<CalendarOverview>(EMPTY_CALENDAR);
  const [devices, setDevices] = useState<Device[]>([]);
  const [cropPlans, setCropPlans] = useState<CropPlan[]>([]);
  const [financePlans, setFinancePlans] = useState<FinancePlan[]>([]);
  const [loading, setLoading] = useState(true);
  const [partial, setPartial] = useState(false);
  const [refreshedAt, setRefreshedAt] = useState<Date | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    const results = await Promise.allSettled([
      api<CalendarOverview>("/calendar/overview", {}, token),
      api<Device[]>("/devices", {}, token),
      api<CropPlan[]>("/crop-planning/plans", {}, token),
      api<FinancePlan[]>("/finance/plans", {}, token),
    ]);
    if (results[0].status === "fulfilled") setCalendar(results[0].value);
    if (results[1].status === "fulfilled") setDevices(results[1].value);
    if (results[2].status === "fulfilled") setCropPlans(results[2].value);
    if (results[3].status === "fulfilled") setFinancePlans(results[3].value);
    setPartial(results.some((result) => result.status === "rejected"));
    setRefreshedAt(new Date());
    setLoading(false);
  }, [token]);

  useEffect(() => { void load(); }, [load]);

  const fields = useMemo(() => farms.flatMap((farm) => farm.fields), [farms]);
  const totalAreaHa = fields.reduce((sum, field) => sum + field.area_m2, 0) / 10000;
  const mappedFarms = farms.filter((farm) => farm.latitude != null && farm.longitude != null).length;
  const assignedDevices = devices.filter((device) => device.field_id != null).length;
  const connectedDevices = devices.filter((device) => device.is_online ?? device.status === "online").length;
  const expectedProfit = financePlans.reduce((sum, plan) => sum + (plan.planned?.expected_profit_rwf || 0), 0);
  const attentionCount = calendar.overdue + calendar.due_today;
  const nextStep = !farms.length ? t("dashboard.addFarm") : !fields.length ? t("dashboard.addField") : !devices.length ? t("dashboard.addDevice") : t("dashboard.allReady");

  const stats: { label: string; value: string | number; note: string; icon: LucideIcon; color: string }[] = [
    { label: t("dashboard.farms"), value: farms.length, note: `${mappedFarms}/${farms.length} ${t("dashboard.mapped").toLocaleLowerCase()}`, icon: Sprout, color: "text-[#91d39a] bg-[#31513a]" },
    { label: t("dashboard.fields"), value: fields.length, note: `${totalAreaHa.toFixed(2)} ha`, icon: LandPlot, color: "text-[#d9c27a] bg-[#50462b]" },
    { label: t("dashboard.devices"), value: devices.length, note: `${connectedDevices} ${t("dashboard.connected")}`, icon: Cpu, color: "text-[#8ab5ee] bg-[#2e4254]" },
    { label: t("dashboard.attention"), value: attentionCount, note: attentionCount ? `${calendar.overdue} ${t("dashboard.overdue").toLocaleLowerCase()}` : t("dashboard.noUrgent"), icon: attentionCount ? AlertTriangle : CheckCircle2, color: attentionCount ? "text-[#edb777] bg-[#563c29]" : "text-[#91d39a] bg-[#31513a]" },
  ];

  const actions: { target: DashboardTarget; label: string; note: string; icon: LucideIcon; color: string }[] = [
    { target: "weather", label: t("dashboard.weatherAction"), note: t("nav.weather"), icon: CloudSun, color: "from-[#384d69] to-[#29364d] text-[#a9c9f6]" },
    { target: "soil", label: t("dashboard.soilAction"), note: t("nav.soil"), icon: FlaskConical, color: "from-[#46502f] to-[#303722] text-[#d4df8c]" },
    { target: "irrigation", label: t("dashboard.irrigationAction"), note: t("nav.irrigation"), icon: Waves, color: "from-[#2f5350] to-[#243a39] text-[#91d8c7]" },
    { target: "planning", label: t("dashboard.planAction"), note: t("nav.planning"), icon: Wheat, color: "from-[#4f4c2d] to-[#383522] text-[#e0cf7f]" },
    { target: "plant-lens", label: t("dashboard.plantAction"), note: t("nav.plantLens"), icon: ScanSearch, color: "from-[#3f5230] to-[#2b3a25] text-[#b7dc8a]" },
    { target: "satellite", label: t("dashboard.satelliteAction"), note: t("nav.satellite"), icon: Satellite, color: "from-[#3c4930] to-[#293324] text-[#bdd783]" },
  ];

  return (
    <div className="dashboard-atmosphere">
      <section className="theme-on-dark relative isolate overflow-hidden rounded-3xl border border-[#536957] bg-[#26382d] p-5 shadow-2xl shadow-black/20 sm:p-8">
        <div aria-hidden="true" className="absolute inset-0 -z-20 bg-cover bg-[center_58%]" style={{ backgroundImage: "url('/rwanda-farm-dashboard.jpg')" }}/>
        <div aria-hidden="true" className="absolute inset-0 -z-10 bg-[linear-gradient(90deg,rgba(14,31,20,.94)_0%,rgba(18,38,25,.86)_48%,rgba(21,43,28,.48)_100%)]"/>
        <div aria-hidden="true" className="absolute inset-0 -z-10 bg-gradient-to-t from-[#14251a]/80 via-transparent to-black/15"/>
        <div className="flex flex-wrap items-start justify-between gap-5">
          <div>
            <h1 className="max-w-3xl text-2xl font-semibold leading-tight sm:text-4xl">{t("dashboard.title")}</h1>
            <p className="mobile-secondary mt-3 max-w-2xl text-sm leading-6 text-[#d8e3da] drop-shadow-sm">{t("dashboard.subtitle")}</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="hidden text-right drop-shadow sm:block"><p className="text-xs text-[#d4e1d6]">{new Date().toLocaleDateString(locale, { weekday: "long", day: "numeric", month: "long" })}</p><p className="mt-1 text-xs text-[#a9bbaa]">{refreshedAt ? t("dashboard.updated") : t("dashboard.loading")}</p></div>
            <button onClick={() => void load()} disabled={loading} aria-label={t("dashboard.refresh")} className="grid h-11 w-11 place-items-center rounded-xl border border-white/20 bg-black/25 text-[#e1ebe2] backdrop-blur-sm hover:bg-black/35 disabled:opacity-50"><RefreshCw size={18} className={loading ? "animate-spin" : ""}/></button>
          </div>
        </div>
        <div className="mt-6 flex items-center gap-3 rounded-2xl border border-white/15 bg-[#101b14]/70 p-4 shadow-lg backdrop-blur-md">
          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-[#8ac46b]/15 text-[#b8dc91]"><TrendingUp size={20}/></span>
          <div className="min-w-0"><p className="text-xs uppercase tracking-wider text-[#8fa096]">{t("dashboard.nextStep")}</p><strong className="mt-1 block truncate text-sm text-[#e2eadf]">{nextStep}</strong></div>
          <button onClick={() => onOpen("farms")} className="ml-auto hidden min-h-10 items-center gap-1 rounded-xl bg-[#92bf6e] px-4 text-sm font-bold text-[#192219] sm:flex">{t("dashboard.openFarms")}<ArrowRight size={16}/></button>
        </div>
      </section>

      {partial && <div role="alert" className="mt-4 flex items-center gap-2 rounded-xl border border-[#6b5738] bg-[#342d22] p-3 text-sm text-[#e1c28a]"><AlertTriangle size={17}/>{t("dashboard.partial")}</div>}

      <section className="mt-5 grid grid-cols-1 gap-3 min-[390px]:grid-cols-2 xl:grid-cols-4">
        {stats.map((stat) => <article key={stat.label} className="rounded-2xl border border-[#3b443e] bg-[#222724] p-4 sm:p-5"><div className="flex items-start justify-between gap-3"><p className="text-xs uppercase tracking-wider text-[#909a92]">{stat.label}</p><span className={`grid h-9 w-9 shrink-0 place-items-center rounded-xl ${stat.color}`}><stat.icon size={18}/></span></div><strong className="mt-4 block text-2xl sm:text-3xl">{loading ? <LoaderCircle className="animate-spin text-[#718078]" size={22}/> : stat.value}</strong><p className="mt-1 truncate text-xs text-[#818b83]">{stat.note}</p></article>)}
      </section>

      <section className="mt-5 grid gap-5 xl:grid-cols-[1.15fr_.85fr]">
        <article className="rounded-2xl border border-[#3b443e] bg-[#222724] p-5">
          <div className="flex items-center justify-between"><div><h2 className="font-semibold">{t("dashboard.attention")}</h2><p className="mt-1 text-xs text-[#879188]">{t("dashboard.quickHelp")}</p></div><CalendarDays className="text-[#c4d77a]" size={20}/></div>
          <div className="mt-5 grid grid-cols-1 gap-2 min-[390px]:grid-cols-3">
            {[[t("dashboard.overdue"), calendar.overdue, "text-[#e9a777]"], [t("dashboard.dueToday"), calendar.due_today, "text-[#e5cc78]"], [t("dashboard.upcoming"), calendar.upcoming_7_days, "text-[#a8d58e]"]].map(([label, value, color]) => <div key={String(label)} className="rounded-xl bg-[#292f2b] p-3"><strong className={`block text-2xl ${color}`}>{value}</strong><span className="mt-1 block text-[11px] leading-4 text-[#929b94]">{label}</span></div>)}
          </div>
          <button onClick={() => onOpen("calendar")} className="mt-4 flex w-full min-h-11 items-center justify-center gap-2 rounded-xl border border-[#4d5b50] text-sm font-semibold hover:bg-[#2b332d]">{t("dashboard.openCalendar")}<ArrowRight size={16}/></button>
        </article>

        <article className="rounded-2xl border border-[#3b443e] bg-[#222724] p-5">
          <div className="flex items-center justify-between"><h2 className="font-semibold">{t("dashboard.systemReady")}</h2><CheckCircle2 className="text-[#8dcc82]" size={20}/></div>
          <div className="mt-5 space-y-4">
            <Readiness label={t("dashboard.fieldsReady")} value={fields.length} total={fields.length}/>
            <Readiness label={t("dashboard.devicesAssigned")} value={assignedDevices} total={devices.length}/>
            <Readiness label={t("dashboard.mapped")} value={mappedFarms} total={farms.length}/>
          </div>
          <button onClick={() => onOpen("devices")} className="mt-5 flex items-center gap-2 text-sm font-semibold text-[#9ed08c] hover:underline"><Cpu size={16}/>{t("dashboard.deviceAction")}<ArrowRight size={14}/></button>
        </article>
      </section>

      <section className="mt-7">
        <div><h2 className="text-xl font-semibold">{t("dashboard.quick")}</h2><p className="mt-1 text-sm text-[#909a92]">{t("dashboard.quickHelp")}</p></div>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {actions.map((action) => <button key={action.target} onClick={() => onOpen(action.target)} className={`group flex min-h-28 items-center gap-4 rounded-2xl border border-white/5 bg-gradient-to-br ${action.color} p-4 text-left transition hover:-translate-y-0.5 hover:border-white/15`}><span className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-black/15"><action.icon size={23}/></span><span className="min-w-0 flex-1"><strong className="block text-sm text-white">{action.label}</strong><small className="mt-1 block truncate text-white/55">{action.note}</small></span><ArrowRight size={17} className="text-white/35 transition group-hover:translate-x-1 group-hover:text-white/75"/></button>)}
        </div>
      </section>

      <section className="mt-7 grid gap-5 lg:grid-cols-[1.1fr_.9fr]">
        <article className="rounded-2xl border border-[#3b443e] bg-[#222724] p-5"><div className="flex items-center justify-between"><h2 className="font-semibold">{t("dashboard.farmOverview")}</h2><button onClick={() => onOpen("farms")} className="flex items-center gap-1 text-xs font-semibold text-[#9ed08c]">{t("dashboard.openFarms")}<ArrowRight size={14}/></button></div><div className="mt-4 space-y-2">{farms.length ? farms.slice(0, 4).map((farm) => <button key={farm.id} onClick={() => onOpen("farms")} className="flex w-full items-center gap-3 rounded-xl bg-[#292f2b] p-3 text-left hover:bg-[#303832]"><span className="grid h-10 w-10 place-items-center rounded-xl bg-[#38513b] text-[#9dd193]"><LandPlot size={18}/></span><span className="min-w-0 flex-1"><strong className="block truncate text-sm">{farm.name}</strong><small className="mt-0.5 block truncate text-[#8d978f]">{farm.district} · {farm.fields.length} {t("farm.fields").toLocaleLowerCase()}</small></span>{farm.latitude != null ? <MapPinned size={16} className="text-[#88c882]"/> : <AlertTriangle size={16} className="text-[#c9a56b]"/>}</button>) : <EmptyState icon={LandPlot} text={t("dashboard.addFarm")}/>}</div></article>
        <article className="rounded-2xl border border-[#3b443e] bg-[#222724] p-5"><div className="flex items-center justify-between"><h2 className="font-semibold">{t("dashboard.financial")}</h2><WalletCards className="text-[#d6b96e]" size={20}/></div><div className="mt-5 grid grid-cols-2 gap-3"><Metric label={t("dashboard.cropPlans")} value={String(cropPlans.length)}/><Metric label={t("dashboard.financePlans")} value={String(financePlans.length)}/></div><div className="mt-3 rounded-xl bg-[#2d3028] p-4"><p className="text-xs text-[#969c8f]">{t("dashboard.expectedProfit")}</p><strong className={`mt-2 block text-xl ${expectedProfit < 0 ? "text-[#e5a07d]" : "text-[#bdd77e]"}`}>{financePlans.length ? formatRwf(expectedProfit, locale) : t("dashboard.noFinancial")}</strong></div><button onClick={() => onOpen("finance")} className="mt-4 flex w-full min-h-11 items-center justify-center gap-2 rounded-xl bg-[#baa45c] text-sm font-bold text-[#242014]">{t("dashboard.openFinance")}<ArrowRight size={16}/></button></article>
      </section>
    </div>
  );
}

function Readiness({ label, value, total }: { label: string; value: number; total: number }) {
  const percentage = total ? Math.min(100, Math.round(value / total * 100)) : 0;
  return <div><div className="flex items-center justify-between gap-3 text-xs"><span className="text-[#a8b1aa]">{label}</span><strong>{value}/{total}</strong></div><div className="mt-2 h-1.5 overflow-hidden rounded-full bg-[#343b36]"><div className="h-full rounded-full bg-gradient-to-r from-[#5aa768] to-[#b5cd71]" style={{ width: `${percentage}%` }}/></div></div>;
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="rounded-xl bg-[#292f2b] p-4"><strong className="block text-2xl">{value}</strong><span className="mt-1 block text-xs text-[#8c968e]">{label}</span></div>;
}

function EmptyState({ icon: Icon, text }: { icon: LucideIcon; text: string }) {
  return <div className="grid min-h-40 place-items-center rounded-xl border border-dashed border-[#465048] p-6 text-center"><div><Icon className="mx-auto text-[#77827a]" size={28}/><p className="mt-3 text-sm text-[#929b94]">{text}</p></div></div>;
}
