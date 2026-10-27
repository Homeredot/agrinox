"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  Bell,
  CalendarDays,
  Check,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock3,
  ExternalLink,
  ListTodo,
  LoaderCircle,
  Mail,
  Pencil,
  Plus,
  Repeat2,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";

import { api, type Farm } from "@/lib/api";

type Task = {
  id: number;
  field_id: number;
  crop_plan_id?: number | null;
  field_name: string;
  farm_id: number;
  farm_name: string;
  title: string;
  description?: string | null;
  category: string;
  category_label: string;
  crop?: string | null;
  growth_stage?: string | null;
  due_at: string;
  reminder_at?: string | null;
  recurrence: "none" | "daily" | "weekly" | "monthly";
  recurrence_interval: number;
  status: "pending" | "completed";
  completed_at?: string | null;
  email_reminder: boolean;
  source_type: "manual" | "suggested";
  source_title?: string | null;
  source_url?: string | null;
};

type Overview = {
  due_today: number;
  overdue: number;
  upcoming_7_days: number;
  completed_this_month: number;
  total_tasks: number;
  email_notifications: { configured: boolean; message: string };
};

type Suggestion = Omit<Task, "id" | "field_id" | "field_name" | "farm_id" | "farm_name" | "category_label" | "status" | "completed_at" | "email_reminder"> & {
  reminder_at: string;
  evidence_note: string;
  confidence: string;
};

type FormState = {
  field_id: string;
  title: string;
  description: string;
  category: string;
  crop: string;
  growth_stage: string;
  due_date: string;
  due_time: string;
  reminder_date: string;
  reminder_time: string;
  recurrence: "none" | "daily" | "weekly" | "monthly";
  recurrence_interval: string;
  email_reminder: boolean;
};

const CATEGORIES = [
  ["soil_preparation", "Soil preparation"], ["planting", "Planting"],
  ["fertilizer_assessment", "Fertilizer assessment"], ["irrigation", "Irrigation"],
  ["pest_scouting", "Pest scouting"], ["field_maintenance", "Field maintenance"],
  ["harvesting", "Harvesting"], ["post_harvest", "Post-harvest storage"],
] as const;

const CATEGORY_COLOR: Record<string, string> = {
  soil_preparation: "bg-[#78654a]", planting: "bg-[#5e873f]", fertilizer_assessment: "bg-[#8a7132]",
  irrigation: "bg-[#34758a]", pest_scouting: "bg-[#9a573f]", field_maintenance: "bg-[#637b43]",
  harvesting: "bg-[#a57830]", post_harvest: "bg-[#735887]",
};

const CROPS = ["Beans", "Irish potatoes", "Maize", "Rice", "Tomato", "Wheat"];
const input = "w-full rounded-xl border border-[#465049] bg-[#232824] px-3 py-2.5 text-sm text-white outline-none focus:border-[#87a85b]";

function dateKey(value: string | Date) {
  const date = typeof value === "string" ? new Date(value) : value;
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function todayKey() { return dateKey(new Date()); }
function localParts(value: string) {
  const date = new Date(value);
  return { date: dateKey(date), time: `${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}` };
}
function iso(date: string, time: string) { return `${date}T${time || "08:00"}:00+02:00`; }
function emptyForm(fieldId: number | undefined, date = todayKey()): FormState {
  return { field_id: fieldId ? String(fieldId) : "", title: "", description: "", category: "field_maintenance", crop: "", growth_stage: "", due_date: date, due_time: "08:00", reminder_date: "", reminder_time: "08:00", recurrence: "none", recurrence_interval: "1", email_reminder: true };
}

export default function FarmingCalendar({ farms, token }: { farms: Farm[]; token: string }) {
  const fields = useMemo(() => farms.flatMap((farm) => farm.fields.map((field) => ({ ...field, farmName: farm.name }))), [farms]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [reminders, setReminders] = useState<Task[]>([]);
  const [fieldFilter, setFieldFilter] = useState("");
  const [month, setMonth] = useState(() => new Date(new Date().getFullYear(), new Date().getMonth(), 1));
  const [editing, setEditing] = useState<Task | "new" | null>(null);
  const [form, setForm] = useState<FormState>(() => emptyForm(fields[0]?.id));
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [suggestionForm, setSuggestionForm] = useState({ field_id: fields[0] ? String(fields[0].id) : "", crop: fields[0]?.crop_note || "Maize", planting_date: todayKey(), growth_stage: "" });
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load() {
    try {
      const suffix = fieldFilter ? `?field_id=${fieldFilter}` : "";
      const [items, summary, alerts] = await Promise.all([
        api<Task[]>(`/calendar/tasks${suffix}`, {}, token),
        api<Overview>("/calendar/overview", {}, token),
        api<Task[]>("/calendar/reminders", {}, token),
      ]);
      setTasks(items); setOverview(summary); setReminders(alerts); setError("");
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : "Could not load the farming calendar"); }
    finally { setLoading(false); }
  }

  useEffect(() => { void load(); }, [fieldFilter, token]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    const timer = window.setInterval(() => { void api<Task[]>("/calendar/reminders", {}, token).then(setReminders).catch(() => undefined); }, 60000);
    return () => window.clearInterval(timer);
  }, [token]);
  useEffect(() => {
    if (!form.field_id && fields[0]) setForm((current) => ({ ...current, field_id: String(fields[0].id) }));
    if (!suggestionForm.field_id && fields[0]) setSuggestionForm((current) => ({ ...current, field_id: String(fields[0].id), crop: fields[0].crop_note || current.crop }));
  }, [fields, form.field_id, suggestionForm.field_id]);

  const byDay = useMemo(() => tasks.reduce<Record<string, Task[]>>((result, task) => {
    (result[dateKey(task.due_at)] ??= []).push(task); return result;
  }, {}), [tasks]);
  const days = useMemo(() => {
    const firstWeekday = month.getDay();
    const count = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate();
    return [...Array(firstWeekday).fill(null), ...Array.from({ length: count }, (_, index) => new Date(month.getFullYear(), month.getMonth(), index + 1))];
  }, [month]);
  const upcoming = useMemo(() => [...tasks].filter((task) => task.status === "pending").sort((a, b) => +new Date(a.due_at) - +new Date(b.due_at)).slice(0, 8), [tasks]);

  function openNew(date = todayKey()) { setForm(emptyForm(Number(fieldFilter) || fields[0]?.id, date)); setEditing("new"); }
  function openEdit(task: Task) {
    const due = localParts(task.due_at); const reminder = task.reminder_at ? localParts(task.reminder_at) : null;
    setForm({ field_id: String(task.field_id), title: task.title, description: task.description || "", category: task.category, crop: task.crop || "", growth_stage: task.growth_stage || "", due_date: due.date, due_time: due.time, reminder_date: reminder?.date || "", reminder_time: reminder?.time || "08:00", recurrence: task.recurrence, recurrence_interval: String(task.recurrence_interval), email_reminder: task.email_reminder });
    setEditing(task);
  }

  async function save(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    const body = { field_id: Number(form.field_id), title: form.title, description: form.description || null, category: form.category, crop: form.crop || null, growth_stage: form.growth_stage || null, due_at: iso(form.due_date, form.due_time), reminder_at: form.reminder_date ? iso(form.reminder_date, form.reminder_time) : null, recurrence: form.recurrence, recurrence_interval: Number(form.recurrence_interval), email_reminder: true };
    try {
      if (editing === "new") await api<Task>("/calendar/tasks", { method: "POST", body: JSON.stringify(body) }, token);
      else if (editing) { const { field_id: _fieldId, ...update } = body; await api<Task>(`/calendar/tasks/${editing.id}`, { method: "PATCH", body: JSON.stringify(update) }, token); }
      setEditing(null); await load();
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : "Could not save task"); }
    finally { setBusy(false); }
  }

  async function complete(task: Task) {
    setBusy(true);
    try { await api(`/calendar/tasks/${task.id}/${task.status === "completed" ? "reopen" : "complete"}`, { method: "POST" }, token); await load(); }
    catch (requestError) { setError(requestError instanceof Error ? requestError.message : "Could not update task"); }
    finally { setBusy(false); }
  }

  async function remove(task: Task) {
    if (!window.confirm(`Delete “${task.title}”?`)) return;
    setBusy(true);
    try { await api(`/calendar/tasks/${task.id}`, { method: "DELETE" }, token); setEditing(null); await load(); }
    catch (requestError) { setError(requestError instanceof Error ? requestError.message : "Could not delete task"); }
    finally { setBusy(false); }
  }

  async function dismiss(task: Task) {
    await api(`/calendar/tasks/${task.id}/dismiss-reminder`, { method: "POST" }, token);
    setReminders((current) => current.filter((item) => item.id !== task.id));
  }

  async function generateSuggestions(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try { setSuggestions(await api<Suggestion[]>("/calendar/suggestions", { method: "POST", body: JSON.stringify({ ...suggestionForm, field_id: Number(suggestionForm.field_id), growth_stage: suggestionForm.growth_stage || null }) }, token)); }
    catch (requestError) { setError(requestError instanceof Error ? requestError.message : "Could not prepare suggestions"); }
    finally { setBusy(false); }
  }

  async function addSuggestion(item: Suggestion) {
    setBusy(true);
    try {
      await api("/calendar/tasks", { method: "POST", body: JSON.stringify({ field_id: Number(suggestionForm.field_id), title: item.title, description: item.description, category: item.category, crop: item.crop, growth_stage: item.growth_stage, due_at: item.due_at, reminder_at: item.reminder_at, recurrence: item.recurrence, recurrence_interval: item.recurrence_interval, email_reminder: true, source_type: "suggested", source_title: item.source_title, source_url: item.source_url }) }, token);
      setSuggestions((current) => current.filter((candidate) => candidate.title !== item.title)); await load();
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : "Could not add suggested task"); }
    finally { setBusy(false); }
  }

  if (loading) return <div className="grid min-h-[65vh] place-items-center"><LoaderCircle className="animate-spin text-[#b7d875]" size={38} /></div>;

  return (
    <div className="space-y-6">
      <header className="theme-on-dark relative overflow-hidden rounded-3xl border border-[#466044] bg-[radial-gradient(circle_at_85%_10%,#42643c_0%,#27372b_35%,#202622_75%)] p-4 sm:p-8">
        <div className="absolute -right-12 -top-16 h-64 w-64 rounded-full border border-[#a8d77b33] shadow-[0_0_100px_#8ecf6330]" />
        <div className="relative flex flex-wrap items-end justify-between gap-5">
          <div><h1 className="text-2xl font-semibold sm:text-4xl">Know what needs attention next</h1><p className="mobile-secondary mt-3 max-w-2xl text-sm leading-6 text-[#bdc9bf]">Plan field work, receive reminders, and turn crop guidance into practical tasks.</p></div>
          <button onClick={() => openNew()} disabled={!fields.length} className="flex items-center gap-2 rounded-xl bg-[#b4d878] px-4 py-3 font-bold text-[#1e2a1d] disabled:opacity-40"><Plus size={18} /> Add task</button>
        </div>
      </header>

      {error && <div role="alert" className="flex items-center justify-between rounded-xl border border-[#7a4941] bg-[#3a2826] p-4 text-[#ffc4b8]"><span className="flex items-center gap-2"><AlertTriangle size={18} />{error}</span><button onClick={() => setError("")}><X size={18} /></button></div>}
      {!fields.length && <div className="rounded-2xl border border-[#685b39] bg-[#332f24] p-5 text-[#ead59b]">Create a farm and at least one field before adding calendar tasks.</div>}

      {!!reminders.length && <section className="rounded-2xl border border-[#8c7038] bg-[#352f22] p-4"><div className="flex items-center gap-2 font-semibold text-[#f0ce83]"><Bell size={18} /> Reminders needing attention</div><div className="mt-3 grid gap-2 sm:grid-cols-2">{reminders.slice(0, 4).map((task) => <div key={task.id} className="flex items-center justify-between gap-3 rounded-xl bg-[#262923] p-3"><button onClick={() => openEdit(task)} className="min-w-0 text-left"><strong className="block truncate text-sm">{task.title}</strong><span className="text-xs text-[#aeb4aa]">{task.field_name} · {new Date(task.due_at).toLocaleString([], { dateStyle: "medium", timeStyle: "short" })}</span></button><button onClick={() => void dismiss(task)} className="rounded-lg border border-[#52584e] px-2 py-1 text-xs">Dismiss</button></div>)}</div></section>}

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Metric label="Due today" value={overview?.due_today ?? 0} icon={<Clock3 size={19} />} tone="text-[#f2cd78]" />
        <Metric label="Next 7 days" value={overview?.upcoming_7_days ?? 0} icon={<ListTodo size={19} />} tone="text-[#b8d979]" />
        <Metric label="Overdue" value={overview?.overdue ?? 0} icon={<AlertTriangle size={19} />} tone="text-[#f29a78]" />
        <Metric label="Completed this month" value={overview?.completed_this_month ?? 0} icon={<CheckCircle2 size={19} />} tone="text-[#78c99a]" />
      </section>

      <div className="grid gap-6 2xl:grid-cols-[1fr_330px]">
        <section className="overflow-hidden rounded-3xl border border-[#3e4941] bg-[#202522]">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#394139] p-4 sm:p-5">
            <div className="flex items-center gap-2"><button onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() - 1, 1))} className="grid h-9 w-9 place-items-center rounded-lg border border-[#475049]"><ChevronLeft size={18} /></button><button onClick={() => setMonth(new Date())} className="rounded-lg border border-[#475049] px-3 py-2 text-xs font-semibold">Today</button><button onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() + 1, 1))} className="grid h-9 w-9 place-items-center rounded-lg border border-[#475049]"><ChevronRight size={18} /></button></div>
            <h2 className="text-lg font-semibold">{month.toLocaleDateString([], { month: "long", year: "numeric" })}</h2>
            <select value={fieldFilter} onChange={(event) => setFieldFilter(event.target.value)} className="rounded-lg border border-[#475049] bg-[#272c28] px-3 py-2 text-sm"><option value="">All fields</option>{fields.map((field) => <option key={field.id} value={field.id}>{field.farmName} · {field.name}</option>)}</select>
          </div>
          <div className="grid grid-cols-7 border-b border-[#394139] bg-[#252b26]">{["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((day) => <div key={day} className="px-1 py-2 text-center text-[10px] font-bold uppercase tracking-wider text-[#879087] sm:text-xs">{day}</div>)}</div>
          <div className="grid grid-cols-7">{days.map((day, index) => day ? <button key={dateKey(day)} onClick={() => openNew(dateKey(day))} className={`min-h-24 border-b border-r border-[#343c35] p-1.5 text-left sm:min-h-32 sm:p-2 ${dateKey(day) === todayKey() ? "bg-[#2b382a]" : "hover:bg-[#262c27]"}`}><span className={`grid h-6 w-6 place-items-center rounded-full text-xs ${dateKey(day) === todayKey() ? "bg-[#b5d779] font-bold text-[#1d281d]" : "text-[#b8beb8]"}`}>{day.getDate()}</span><div className="mt-1 space-y-1">{(byDay[dateKey(day)] || []).slice(0, 3).map((task) => <span key={task.id} onClick={(event) => { event.stopPropagation(); openEdit(task); }} className={`block truncate rounded px-1.5 py-1 text-[10px] text-white ${CATEGORY_COLOR[task.category] || "bg-[#59635b]"} ${task.status === "completed" ? "opacity-45 line-through" : ""}`}>{task.title}</span>)}{(byDay[dateKey(day)] || []).length > 3 && <span className="block text-[10px] text-[#929a92]">+{byDay[dateKey(day)].length - 3} more</span>}</div></button> : <div key={`blank-${index}`} className="min-h-24 border-b border-r border-[#343c35] bg-[#1d211e] sm:min-h-32" />)}</div>
        </section>

        <aside className="space-y-4">
          <section className="rounded-3xl border border-[#4c573f] bg-[#242b23] p-5"><div className="flex items-start justify-between gap-3"><div><p className="flex items-center gap-2 text-sm font-semibold text-[#c4e08e]"><Sparkles size={17} /> Crop-stage suggestions</p><p className="mt-2 text-xs leading-5 text-[#99a398]">Creates an editable plan from the planting date. Confirm timing against weather and local advice.</p></div><button onClick={() => setShowSuggestions((value) => !value)} className="rounded-lg bg-[#35452f] px-3 py-2 text-xs font-semibold">{showSuggestions ? "Close" : "Plan"}</button></div>
            {showSuggestions && <form onSubmit={generateSuggestions} className="mt-4 space-y-3"><select required value={suggestionForm.field_id} onChange={(event) => { const selectedField = fields.find((field) => field.id === Number(event.target.value)); setSuggestionForm((current) => ({ ...current, field_id: event.target.value, crop: selectedField?.crop_note || current.crop })); }} className={input}><option value="">Choose field</option>{fields.map((field) => <option key={field.id} value={field.id}>{field.farmName} · {field.name}</option>)}</select><select value={suggestionForm.crop} onChange={(event) => setSuggestionForm((current) => ({ ...current, crop: event.target.value }))} className={input}>{CROPS.map((crop) => <option key={crop}>{crop}</option>)}</select><label className="block text-xs text-[#aab2aa]">Planned planting date<input type="date" value={suggestionForm.planting_date} onChange={(event) => setSuggestionForm((current) => ({ ...current, planting_date: event.target.value }))} className={`${input} mt-1`} /></label><select value={suggestionForm.growth_stage} onChange={(event) => setSuggestionForm((current) => ({ ...current, growth_stage: event.target.value }))} className={input}><option value="">Full crop plan</option><option value="establishment">Establishment</option><option value="vegetative">Vegetative</option><option value="maturity">Maturity / harvest</option></select><button disabled={busy} className="flex w-full items-center justify-center gap-2 rounded-xl bg-[#91b65b] px-4 py-2.5 font-bold text-[#182017] disabled:opacity-50">{busy ? <LoaderCircle className="animate-spin" size={17} /> : <Sparkles size={17} />} Build suggestions</button></form>}
          </section>

          <section className="rounded-3xl border border-[#414841] bg-[#222723] p-5"><h2 className="font-semibold">Next tasks</h2><div className="mt-3 space-y-2">{upcoming.map((task) => <button key={task.id} onClick={() => openEdit(task)} className="w-full rounded-xl border border-[#3b443d] bg-[#272d28] p-3 text-left hover:border-[#63705c]"><div className="flex items-start gap-2"><span className={`mt-1 h-2.5 w-2.5 shrink-0 rounded-full ${CATEGORY_COLOR[task.category]}`} /><div className="min-w-0"><strong className="block truncate text-sm">{task.title}</strong><p className="mt-1 text-xs text-[#919a92]">{new Date(task.due_at).toLocaleDateString([], { month: "short", day: "numeric" })} · {task.field_name}{task.crop_plan_id ? " · Crop plan" : ""}</p></div></div></button>)}{!upcoming.length && <p className="py-6 text-center text-sm text-[#858e86]">No upcoming tasks.</p>}</div></section>
          <div className="rounded-2xl border border-[#3e4941] bg-[#222723] p-4 text-xs text-[#9aa39a]"><p className="flex items-center gap-2 font-semibold text-[#c5cbc5]"><Mail size={15} /> Automatic email reminders</p><p className="mt-2 leading-5">{overview?.email_notifications.message}</p></div>
        </aside>
      </div>

      {!!suggestions.length && <section className="rounded-3xl border border-[#556746] bg-[#232b22] p-5 sm:p-6"><div className="flex items-center justify-between gap-3"><div><h2 className="text-xl font-semibold">Suggested field plan</h2><p className="mt-1 text-sm text-[#9ca79b]">Review each item before adding it to your calendar.</p></div><button onClick={() => setSuggestions([])}><X /></button></div><div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-4">{suggestions.map((item) => <article key={`${item.category}-${item.due_at}`} className="flex flex-col rounded-2xl border border-[#43503e] bg-[#282f27] p-4"><div className="flex items-center justify-between gap-2"><span className="rounded-full bg-[#35432f] px-2 py-1 text-[10px] font-bold uppercase text-[#bad88c]">{item.growth_stage}</span><span className="text-xs text-[#9aa49a]">{new Date(item.due_at).toLocaleDateString([], { month: "short", day: "numeric" })}</span></div><h3 className="mt-3 font-semibold">{item.title}</h3><p className="mt-2 flex-1 text-xs leading-5 text-[#a9b1a8]">{item.description}</p><p className="mt-3 text-[10px] leading-4 text-[#889288]">{item.evidence_note}</p><div className="mt-4 flex items-center justify-between"><a href={item.source_url || "#"} target="_blank" rel="noreferrer" className="flex items-center gap-1 text-xs text-[#d1b66c]">Source <ExternalLink size={11} /></a><button disabled={busy} onClick={() => void addSuggestion(item)} className="rounded-lg bg-[#85a953] px-3 py-2 text-xs font-bold text-[#182016]">Add task</button></div></article>)}</div></section>}

      {editing && <div className="fixed inset-0 z-[1400] overflow-y-auto bg-black/70 p-4 backdrop-blur-sm" onClick={() => setEditing(null)}><form onSubmit={save} onClick={(event) => event.stopPropagation()} className="mx-auto my-8 max-w-2xl rounded-3xl border border-[#485149] bg-[#202521] p-5 shadow-2xl sm:p-7"><div className="flex items-start justify-between"><div><p className="text-xs font-bold uppercase tracking-[.18em] text-[#a9ce70]">{editing === "new" ? "New calendar task" : "Edit task"}</p><h2 className="mt-2 text-2xl font-semibold">{editing === "new" ? "Plan farm work" : (editing as Task).title}</h2></div><button type="button" onClick={() => setEditing(null)} className="grid h-9 w-9 place-items-center rounded-full bg-[#303630]"><X size={18} /></button></div><div className="mt-6 grid gap-4 sm:grid-cols-2"><label className="text-xs text-[#a7afa7]">Field<select required disabled={editing !== "new"} value={form.field_id} onChange={(event) => setForm((current) => ({ ...current, field_id: event.target.value }))} className={`${input} mt-1 disabled:opacity-60`}><option value="">Choose field</option>{fields.map((field) => <option key={field.id} value={field.id}>{field.farmName} · {field.name}</option>)}</select></label><label className="text-xs text-[#a7afa7]">Task type<select value={form.category} onChange={(event) => setForm((current) => ({ ...current, category: event.target.value }))} className={`${input} mt-1`}>{CATEGORIES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><label className="text-xs text-[#a7afa7] sm:col-span-2">Task title<input required minLength={2} value={form.title} onChange={(event) => setForm((current) => ({ ...current, title: event.target.value }))} className={`${input} mt-1`} placeholder="Example: Scout potatoes for late blight symptoms" /></label><label className="text-xs text-[#a7afa7]">Crop<input value={form.crop} onChange={(event) => setForm((current) => ({ ...current, crop: event.target.value }))} className={`${input} mt-1`} placeholder="Irish potatoes" /></label><label className="text-xs text-[#a7afa7]">Growth stage<input value={form.growth_stage} onChange={(event) => setForm((current) => ({ ...current, growth_stage: event.target.value }))} className={`${input} mt-1`} placeholder="Vegetative" /></label><label className="text-xs text-[#a7afa7]">Due date<input required type="date" value={form.due_date} onChange={(event) => setForm((current) => ({ ...current, due_date: event.target.value }))} className={`${input} mt-1`} /></label><label className="text-xs text-[#a7afa7]">Due time<input required type="time" value={form.due_time} onChange={(event) => setForm((current) => ({ ...current, due_time: event.target.value }))} className={`${input} mt-1`} /></label><label className="text-xs text-[#a7afa7]">Reminder date<input type="date" value={form.reminder_date} max={form.due_date} onChange={(event) => setForm((current) => ({ ...current, reminder_date: event.target.value }))} className={`${input} mt-1`} /></label><label className="text-xs text-[#a7afa7]">Reminder time<input type="time" disabled={!form.reminder_date} value={form.reminder_time} onChange={(event) => setForm((current) => ({ ...current, reminder_time: event.target.value }))} className={`${input} mt-1 disabled:opacity-50`} /></label><label className="text-xs text-[#a7afa7]">Repeat<select value={form.recurrence} onChange={(event) => setForm((current) => ({ ...current, recurrence: event.target.value as FormState["recurrence"] }))} className={`${input} mt-1`}><option value="none">Does not repeat</option><option value="daily">Daily</option><option value="weekly">Weekly</option><option value="monthly">Monthly</option></select></label><label className="text-xs text-[#a7afa7]">Repeat every<input type="number" min="1" max="52" disabled={form.recurrence === "none"} value={form.recurrence_interval} onChange={(event) => setForm((current) => ({ ...current, recurrence_interval: event.target.value }))} className={`${input} mt-1 disabled:opacity-50`} /></label><label className="text-xs text-[#a7afa7] sm:col-span-2">Notes<textarea rows={3} value={form.description} onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))} className={`${input} mt-1 resize-none`} placeholder="What should be checked or recorded?" /></label></div><div className="mt-6 flex flex-wrap items-center justify-between gap-3">{editing !== "new" ? <div className="flex gap-2"><button type="button" disabled={busy} onClick={() => void complete(editing as Task)} className="flex items-center gap-2 rounded-xl border border-[#587150] px-4 py-2.5 text-sm font-semibold text-[#a9d493]">{(editing as Task).status === "completed" ? <Repeat2 size={16} /> : <Check size={16} />}{(editing as Task).status === "completed" ? "Reopen" : "Complete"}</button><button type="button" disabled={busy} onClick={() => void remove(editing as Task)} className="grid h-11 w-11 place-items-center rounded-xl border border-[#704943] text-[#ef9d91]"><Trash2 size={17} /></button></div> : <span />}<button disabled={busy || !form.field_id} className="flex items-center gap-2 rounded-xl bg-[#a8ce6c] px-5 py-2.5 font-bold text-[#172016] disabled:opacity-50">{busy ? <LoaderCircle className="animate-spin" size={17} /> : <Pencil size={17} />}{editing === "new" ? "Create task" : "Save changes"}</button></div></form></div>}
    </div>
  );
}

function Metric({ label, value, icon, tone }: { label: string; value: number; icon: React.ReactNode; tone: string }) {
  return <div className="rounded-2xl border border-[#3d463f] bg-[#222823] p-4"><div className={`flex items-center gap-2 text-xs font-bold uppercase tracking-wider ${tone}`}>{icon}{label}</div><strong className="mt-3 block text-3xl">{value}</strong></div>;
}
