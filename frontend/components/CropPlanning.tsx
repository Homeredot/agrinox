"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { AlertTriangle, BarChart3, CalendarDays, Check, ChevronRight, Database, History, LandPlot, MapPin, Sparkles, Sprout, Wheat } from "lucide-react";
import { api, Farm } from "@/lib/api";

type PlanningOptions = { seasons: { value: "A" | "B" | "C"; label: string; usual_months: string }[]; dataset_version: string };
type CropChoice = { rank: number; label: string; crop: string; yield_range_t_ha: [number, number]; estimated_total_harvest_t: [number, number]; historical_baseline_t_ha: number; district_observations: number; national_observations: number; years: number[]; history_check: "repeat_needs_review" | "different_from_last" | "history_missing"; why: string[]; sources: { key: string; title: string; url: string }[] };
type Recommendations = { field: { id: number; name: string; farm_name: string; district: string; province: string; area_ha: number }; season: "A" | "B" | "C"; planned_planting_date: string; timing_note?: string; last_recorded_crop?: string; crop_history: { crop: string; season?: string; planned_planting_date?: string }[]; recommendations: CropChoice[]; method: string; important_note: string; rotation_reference: { title: string; url: string } };
type PredictionResult = { plan_id: number; status: "baseline_available" | "insufficient_evidence"; message?: string; context: { field_name: string; district: string; area_ha: number }; prediction?: { yield_range_t_ha: [number, number]; estimated_total_harvest_t: [number, number]; historical_baseline_t_ha: number; confidence: string; uncertainty: string }; data_availability: { national_observations: number; district_observations: number; geography_used?: string }; model: { version: string; mae_t_ha?: number; rmse_t_ha?: number; validation_design?: string; training_data_coverage?: string }; why_this_prediction?: string[]; limitations: string[]; sources: { key: string; title: string; url: string }[] };
type SavedPlan = { id: number; crop: string; season: string; farm_name: string; field_name: string; planned_planting_date: string; calendar_task_count: number; result: PredictionResult };
type CalendarLinkResult = { created: boolean; plan_id: number; task_count: number; message: string };

const control = "w-full h-12 px-3.5 rounded-xl border border-[#485047] bg-[#222724] text-[#f4f7f3] outline-none focus:border-[#7ca86a] focus:ring-2 focus:ring-[#7ca86a]/15";
function number(value: number | undefined, digits = 2) { return value == null ? "—" : value.toFixed(digits).replace(/\.00$/, ""); }
function defaultDate() { const next = new Date(); next.setDate(next.getDate() + 14); return next.toISOString().slice(0, 10); }

export default function CropPlanning({ farms, token, onOpenCalendar }: { farms: Farm[]; token: string; onOpenCalendar?: () => void }) {
  const fields = useMemo(() => farms.flatMap((farm) => farm.fields.map((field) => ({ farm, field }))), [farms]);
  const [options, setOptions] = useState<PlanningOptions | null>(null);
  const [plans, setPlans] = useState<SavedPlan[]>([]);
  const [fieldId, setFieldId] = useState<number | null>(fields[0]?.field.id ?? null);
  const [season, setSeason] = useState<"A" | "B" | "C">("A");
  const [plantingDate, setPlantingDate] = useState(defaultDate);
  const [recommendations, setRecommendations] = useState<Recommendations | null>(null);
  const [selectedCrop, setSelectedCrop] = useState<CropChoice | null>(null);
  const [result, setResult] = useState<PredictionResult | null>(null);
  const [resultCrop, setResultCrop] = useState("");
  const [calendarBusy, setCalendarBusy] = useState<number | null>(null);
  const [calendarMessage, setCalendarMessage] = useState("");
  const [irrigation, setIrrigation] = useState("unknown");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const selectedField = fields.find((item) => item.field.id === fieldId) ?? fields[0];

  useEffect(() => {
    Promise.all([api<PlanningOptions>("/crop-planning/options", {}, token), api<SavedPlan[]>("/crop-planning/plans", {}, token)])
      .then(([nextOptions, saved]) => { setOptions(nextOptions); setPlans(saved); })
      .catch((requestError) => setError(requestError instanceof Error ? requestError.message : "Could not load crop planning"));
  }, [token]);

  function resetAdvice() { setRecommendations(null); setSelectedCrop(null); setResult(null); }

  async function findChoices(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!fieldId) return;
    setBusy(true); setError(""); setResult(null);
    try {
      const next = await api<Recommendations>("/crop-planning/recommendations", { method: "POST", body: JSON.stringify({ field_id: fieldId, season, planned_planting_date: plantingDate }) }, token);
      setRecommendations(next); setSelectedCrop(next.recommendations[0] ?? null);
      requestAnimationFrame(() => document.getElementById("crop-choices")?.scrollIntoView({ behavior: "smooth", block: "start" }));
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : "Could not check crop choices"); }
    finally { setBusy(false); }
  }

  async function savePlan() {
    if (!fieldId || !selectedCrop) return;
    setBusy(true); setError("");
    try {
      const prediction = await api<PredictionResult>("/crop-planning/plans", { method: "POST", body: JSON.stringify({ field_id: fieldId, crop: selectedCrop.crop, season, planned_planting_date: plantingDate, irrigation, previous_crop: recommendations?.last_recorded_crop || null }) }, token);
      setResult(prediction); setResultCrop(selectedCrop.crop); setCalendarMessage(""); setPlans(await api<SavedPlan[]>("/crop-planning/plans", {}, token));
      requestAnimationFrame(() => document.getElementById("saved-plan")?.scrollIntoView({ behavior: "smooth", block: "start" }));
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : "Could not save the plan"); }
    finally { setBusy(false); }
  }

  async function addPlanToCalendar(planId: number) {
    setCalendarBusy(planId); setError(""); setCalendarMessage("");
    try {
      const linked = await api<CalendarLinkResult>(`/crop-planning/plans/${planId}/calendar`, { method: "POST" }, token);
      setCalendarMessage(linked.message);
      setPlans((current) => current.map((plan) => plan.id === planId ? { ...plan, calendar_task_count: linked.task_count } : plan));
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : "Could not add the plan to the calendar"); }
    finally { setCalendarBusy(null); }
  }

  return <div className="crop-plan-atmosphere">
    <div><h1 className="text-2xl font-semibold sm:text-4xl">What should I plant next?</h1><p className="mobile-secondary mt-2 max-w-2xl text-[#abb3aa]">Choose a field and planting period. We check verified yield records and your field history.</p></div>
    {error && <div role="alert" className="mt-6 rounded-xl border border-[#70403c] bg-[#3b2523] px-4 py-3 text-[#ffc0b8]">{error}</div>}

    {!fields.length ? <div className="mt-8 rounded-2xl border border-[#665834] bg-[#342f22] p-6 flex gap-4"><AlertTriangle className="text-[#e1bd68] shrink-0" /><div><h2 className="font-semibold">Add a field first</h2><p className="text-sm text-[#c9c2a8] mt-1">The planner gets location and land size from My Farm.</p></div></div> :
      <form onSubmit={findChoices} className="crop-plan-card mt-7 rounded-2xl p-5 sm:p-6 max-w-4xl">
        <div className="flex items-center gap-3 mb-5"><span className="w-10 h-10 rounded-xl grid place-items-center bg-[#9dcc65]/12 text-[#abd675]"><Sprout size={21} /></span><div><h2 className="font-semibold text-lg">Tell us only two things</h2><p className="text-xs text-[#899188] mt-0.5">Your saved farm information is filled automatically.</p></div></div>
        <div className="grid md:grid-cols-3 gap-4">
          <label className="text-sm text-[#cbd1ca]">1. Which field?<select className={`${control} mt-2`} value={fieldId ?? ""} onChange={(event) => { setFieldId(Number(event.target.value)); resetAdvice(); }}>{fields.map(({ farm, field }) => <option key={field.id} value={field.id}>{farm.name} · {field.name}</option>)}</select></label>
          <label className="text-sm text-[#cbd1ca]">2. Which season?<select className={`${control} mt-2`} value={season} onChange={(event) => { setSeason(event.target.value as "A" | "B" | "C"); resetAdvice(); }}>{options?.seasons.map((item) => <option key={item.value} value={item.value}>{item.label} · {item.usual_months}</option>)}</select></label>
          <label className="text-sm text-[#cbd1ca]">Planting date<input className={`${control} mt-2`} type="date" value={plantingDate} onChange={(event) => { setPlantingDate(event.target.value); resetAdvice(); }} required /></label>
        </div>
        {selectedField && <div className="mt-4 flex flex-wrap gap-x-6 gap-y-2 text-xs text-[#9fa89e]"><span className="flex items-center gap-1.5"><MapPin size={14} />{selectedField.farm.district}, {selectedField.farm.province}</span><span className="flex items-center gap-1.5"><LandPlot size={14} />{(selectedField.field.area_m2 / 10000).toFixed(3)} ha</span><span className="flex items-center gap-1.5"><History size={14} />Saved crop: {selectedField.field.crop_note || "none"}</span></div>}
        <button disabled={busy || !fieldId} className="mt-5 h-12 px-6 rounded-xl bg-gradient-to-r from-[#6c9f48] to-[#277153] hover:brightness-110 disabled:opacity-50 font-semibold flex items-center justify-center gap-2"><Sparkles size={18} />{busy ? "Checking records…" : "Show what I can plant"}</button>
      </form>}

    {recommendations && <section id="crop-choices" className="scroll-mt-24 mt-8">
      <div className="flex flex-wrap items-end justify-between gap-3"><div><p className="text-xs uppercase tracking-[.16em] text-[#a8d36f] font-bold">Your choices</p><h2 className="text-2xl font-semibold mt-1">Best-supported options for Season {recommendations.season}</h2></div><span className="text-sm text-[#9ba49a]">Last recorded crop: <strong className="text-[#dce3da]">{recommendations.last_recorded_crop || "Not recorded"}</strong></span></div>
      {recommendations.timing_note && <div className="mt-4 rounded-xl border border-[#665834] bg-[#342f22] px-4 py-3 text-sm text-[#e0c887] flex gap-2"><CalendarDays size={17} className="shrink-0" />{recommendations.timing_note}</div>}
      <div className="grid lg:grid-cols-3 gap-4 mt-5">{recommendations.recommendations.map((choice) => <button key={choice.crop} type="button" onClick={() => { setSelectedCrop(choice); setResult(null); }} className={`text-left rounded-2xl border p-5 transition ${selectedCrop?.crop === choice.crop ? "border-[#8fbd68] bg-[#2b3729] ring-2 ring-[#8fbd68]/15" : "border-[#424a42] bg-[#242925] hover:border-[#667461]"}`}>
        <div className="flex items-start justify-between gap-3"><span className="text-xs font-bold uppercase tracking-wider text-[#a8d36f]">{choice.label}</span>{selectedCrop?.crop === choice.crop && <span className="w-6 h-6 rounded-full bg-[#82ad60] grid place-items-center"><Check size={14} /></span>}</div>
        <h3 className="text-xl font-semibold mt-3">{choice.crop}</h3><div className="mt-4"><span className="text-2xl font-semibold">{number(choice.estimated_total_harvest_t[0])}–{number(choice.estimated_total_harvest_t[1])}</span><span className="text-xs text-[#9ba49a] ml-2">tonnes total</span></div><p className="text-xs text-[#8f998e] mt-1">{number(choice.yield_range_t_ha[0])}–{number(choice.yield_range_t_ha[1])} t/ha from observed records</p>
        <div className={`mt-4 rounded-lg px-3 py-2 text-xs ${choice.history_check === "repeat_needs_review" ? "bg-[#5b4728]/45 text-[#e5c37a]" : "bg-[#355039]/45 text-[#acd19d]"}`}>{choice.history_check === "repeat_needs_review" ? "Same as last crop — review rotation" : choice.history_check === "different_from_last" ? "Different from last crop" : "No crop history yet"}</div>
        <ul className="mt-4 space-y-2 text-xs leading-5 text-[#adb6ab]">{choice.why.slice(0, 3).map((reason) => <li key={reason}>• {reason}</li>)}</ul>
      </button>)}</div>
      {selectedCrop && <div className="mt-5 crop-plan-card rounded-2xl p-5 flex flex-col lg:flex-row lg:items-end gap-4"><div className="flex-1"><p className="text-xs text-[#8f998e]">Selected crop</p><h3 className="text-xl font-semibold mt-1">{selectedCrop.crop}</h3><p className="text-sm text-[#aab3a8] mt-2">One last check: what water is available?</p></div><label className="text-sm text-[#cbd1ca] lg:w-56">Water<select className={`${control} mt-2`} value={irrigation} onChange={(event) => setIrrigation(event.target.value)}><option value="unknown">Not sure</option><option value="available">Irrigation available</option><option value="limited">Limited water</option><option value="rainfed">Rain-fed only</option></select></label><button type="button" onClick={savePlan} disabled={busy} className="h-12 px-6 rounded-xl bg-[#79a958] hover:bg-[#86b865] disabled:opacity-50 font-semibold flex items-center justify-center gap-2"><Check size={18} />{busy ? "Saving…" : `Use ${selectedCrop.crop}`}</button></div>}
      <details className="mt-4 rounded-xl border border-[#3d443d] bg-[#222724] px-4 py-3 text-sm"><summary className="cursor-pointer font-medium text-[#cbd4c8]">How were these choices selected?</summary><p className="mt-3 text-xs leading-5 text-[#99a298]">{recommendations.method}</p><p className="mt-2 text-xs leading-5 text-[#c9b886]">{recommendations.important_note}</p><a href={recommendations.rotation_reference.url} target="_blank" rel="noreferrer" className="inline-block mt-2 text-xs text-[#9ccf78] hover:underline">{recommendations.rotation_reference.title}</a></details>
    </section>}

    {calendarMessage && <div className="mt-6 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[#557044] bg-[#2b3927] px-4 py-3 text-sm text-[#c5e3a4]"><span className="flex items-center gap-2"><CalendarDays size={17} />{calendarMessage}</span>{onOpenCalendar && <button onClick={onOpenCalendar} className="rounded-lg bg-[#98bd64] px-3 py-2 text-xs font-bold text-[#192118]">View calendar</button>}</div>}
    {result && <SavedResult result={result} crop={resultCrop || selectedCrop?.crop || "Crop"} calendarTaskCount={plans.find((plan) => plan.id === result.plan_id)?.calendar_task_count ?? 0} calendarBusy={calendarBusy === result.plan_id} onAddCalendar={() => void addPlanToCalendar(result.plan_id)} onOpenCalendar={onOpenCalendar} />}
    <section className="mt-8 crop-plan-card rounded-2xl p-5 max-w-4xl"><div className="flex items-center gap-2"><History size={18} className="text-[#a8d36f]" /><h2 className="font-semibold">Previous plans</h2></div><div className="mt-4 space-y-2">{plans.length ? plans.slice(0, 5).map((plan) => <div key={plan.id} className="flex flex-col gap-2 rounded-xl border border-[#3d433e] bg-[#222624] p-3 sm:flex-row sm:items-center sm:p-2"><button type="button" onClick={() => { setResult(plan.result); setResultCrop(plan.crop); setCalendarMessage(""); }} className="min-w-0 flex-1 px-2 py-1 text-left"><strong className="text-sm">{plan.crop} · Season {plan.season}</strong><span className="block truncate text-xs text-[#8f978f] mt-1">{plan.farm_name} / {plan.field_name} · {plan.planned_planting_date}</span></button><button type="button" disabled={calendarBusy === plan.id} onClick={() => plan.calendar_task_count ? onOpenCalendar?.() : void addPlanToCalendar(plan.id)} className={`flex w-full shrink-0 items-center justify-center gap-1.5 rounded-lg px-3 py-2 text-xs font-semibold sm:w-auto ${plan.calendar_task_count ? "bg-[#34442f] text-[#bddd94]" : "border border-[#596551] text-[#b7ce9e]"}`}><CalendarDays size={15} />{plan.calendar_task_count ? `${plan.calendar_task_count} tasks` : "Add to calendar"}</button><ChevronRight size={17} className="hidden text-[#788078] sm:block" /></div>) : <p className="text-sm text-[#858d85]">No saved plan yet.</p>}</div></section>
  </div>;
}

function SavedResult({ result, crop, calendarTaskCount, calendarBusy, onAddCalendar, onOpenCalendar }: { result: PredictionResult; crop: string; calendarTaskCount: number; calendarBusy: boolean; onAddCalendar: () => void; onOpenCalendar?: () => void }) {
  if (!result.prediction) return <section id="saved-plan" className="scroll-mt-24 mt-7 rounded-2xl border border-[#68583c] bg-[#342e22] p-5"><h2 className="font-semibold">Plan saved, but evidence is limited</h2><p className="text-sm text-[#c8bfa8] mt-1">{result.message}</p><button type="button" disabled={calendarBusy} onClick={calendarTaskCount ? onOpenCalendar : onAddCalendar} className="mt-4 flex items-center gap-2 rounded-xl bg-[#a1c96b] px-4 py-2.5 text-sm font-bold text-[#172016] disabled:opacity-50"><CalendarDays size={17} />{calendarBusy ? "Adding tasks…" : calendarTaskCount ? `View ${calendarTaskCount} calendar tasks` : "Add plan to calendar"}</button></section>;
  const prediction = result.prediction;
  return <section id="saved-plan" className="scroll-mt-24 mt-7 crop-plan-result rounded-2xl p-5 sm:p-7"><div className="flex flex-wrap items-start justify-between gap-4"><div><p className="text-xs uppercase tracking-[.18em] text-[#b9e282] font-bold">Plan saved</p><h2 className="text-2xl font-semibold mt-2">{crop} · {result.context.field_name}</h2><p className="text-sm text-[#bcc8b8] mt-1">{result.context.district} · {result.context.area_ha} ha</p></div><span className="rounded-full px-3 py-1.5 text-xs font-semibold bg-[#83b95f]/15 text-[#b9de92]">{prediction.confidence} evidence confidence</span></div>
    <div className="grid sm:grid-cols-3 gap-3 mt-6"><Metric icon={Wheat} label="Expected yield" value={`${number(prediction.yield_range_t_ha[0])}–${number(prediction.yield_range_t_ha[1])}`} unit="t/ha" /><Metric icon={LandPlot} label="Expected harvest" value={`${number(prediction.estimated_total_harvest_t[0])}–${number(prediction.estimated_total_harvest_t[1])}`} unit="tonnes" /><Metric icon={BarChart3} label="Historical middle" value={number(prediction.historical_baseline_t_ha)} unit="t/ha" /></div>
    <div className="mt-5 rounded-xl bg-black/10 border border-white/10 p-4"><h3 className="font-semibold text-sm">Why this estimate?</h3><ul className="mt-2 space-y-1.5 text-xs leading-5 text-[#b6c1b2]">{result.why_this_prediction?.slice(0, 3).map((item) => <li key={item}>• {item}</li>)}</ul></div>
    <div className="mt-5 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[#66814f] bg-[#2a3727] p-4"><div><p className="flex items-center gap-2 font-semibold text-[#c6e69d]"><CalendarDays size={17} />Continue with this plan</p><p className="mt-1 text-xs text-[#9eac99]">Create soil preparation, planting, scouting, maintenance, harvest and storage tasks using this plan&apos;s dates.</p></div><button type="button" disabled={calendarBusy} onClick={calendarTaskCount ? onOpenCalendar : onAddCalendar} className="rounded-xl bg-[#a1c96b] px-4 py-2.5 text-sm font-bold text-[#172016] disabled:opacity-50">{calendarBusy ? "Adding tasks…" : calendarTaskCount ? `View ${calendarTaskCount} calendar tasks` : "Add plan to calendar"}</button></div>
    <details className="mt-4 rounded-xl border border-white/10 px-4 py-3 text-sm"><summary className="cursor-pointer font-medium flex items-center gap-2"><Database size={15} />Technical evidence</summary><div className="mt-3 text-xs leading-5 text-[#a6b1a2]"><p>MAE: {number(result.model.mae_t_ha, 3)} t/ha · RMSE: {number(result.model.rmse_t_ha, 3)} t/ha</p><p className="mt-1">{result.model.validation_design}</p><p className="mt-1">{result.model.training_data_coverage}</p><p className="mt-1">Model: {result.model.version}</p></div></details>
  </section>;
}

function Metric({ icon: Icon, label, value, unit }: { icon: typeof Wheat; label: string; value: string; unit: string }) { return <div className="rounded-2xl border border-white/10 bg-black/10 p-4"><div className="flex items-center gap-2 text-xs text-[#adbaa8]"><Icon size={15} />{label}</div><div className="mt-3"><span className="text-2xl sm:text-3xl font-semibold">{value}</span><span className="text-xs text-[#9daa98] ml-2">{unit}</span></div></div>; }
