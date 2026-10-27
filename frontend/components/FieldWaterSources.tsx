"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { CheckCircle2, Droplets, Gauge, LoaderCircle, Plus, Radio, Star, Trash2, Waves, X } from "lucide-react";

import { api, type Field } from "@/lib/api";
import { useI18n } from "./I18nProvider";

type Level = { raw_value: number; raw_unit?: string | null; recorded_at: string; simulated: boolean; remaining_percent?: number | null; remaining_liters?: number | null; measurement_method?: string | null; limitation?: string | null };
type Source = { id: number; name: string; source_type: string; capacity_liters?: number | null; tank_height_cm?: number | null; sensor_id?: number | null; notes?: string | null; is_primary: boolean; is_active: boolean; latest_level?: Level | null };
type Sensor = { id: number; name: string; key: string; sensor_type: string; unit?: string | null; device_name: string; available: boolean; water_source_id?: number | null };
type Response = { sources: Source[]; compatible_sensors: Sensor[] };

const types = ["tank", "pond", "borehole", "river", "tap", "rainwater", "other"];

export default function FieldWaterSources({ field, token, onClose }: { field: Field; token: string; onClose: () => void }) {
  const { t, locale } = useI18n();
  const [data, setData] = useState<Response | null>(null);
  const [adding, setAdding] = useState(false);
  const [sourceType, setSourceType] = useState("tank");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const load = useCallback(async () => {
    try { setData(await api<Response>(`/fields/${field.id}/water-sources`, {}, token)); setError(""); }
    catch (requestError) { setError(requestError instanceof Error ? requestError.message : t("common.error")); }
  }, [field.id, token, t]);

  useEffect(() => { void load(); }, [load]);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(""); setMessage("");
    const form = event.currentTarget; const values = Object.fromEntries(new FormData(form));
    const payload = {
      name: values.name,
      source_type: values.source_type,
      notes: values.notes || null,
      is_primary: values.is_primary === "on",
      capacity_liters: sourceType === "tank" && values.capacity_liters ? Number(values.capacity_liters) : null,
      tank_height_cm: sourceType === "tank" && values.tank_height_cm ? Number(values.tank_height_cm) : null,
      sensor_id: sourceType === "tank" && values.sensor_id ? Number(values.sensor_id) : null,
    };
    try { await api(`/fields/${field.id}/water-sources`, { method: "POST", body: JSON.stringify(payload) }, token); form.reset(); setSourceType("tank"); setAdding(false); setMessage(t("water.saved")); await load(); }
    catch (requestError) { setError(requestError instanceof Error ? requestError.message : t("common.error")); }
    finally { setBusy(false); }
  }

  async function makePrimary(sourceId: number) {
    setBusy(true); setError("");
    try { await api(`/fields/${field.id}/water-sources/${sourceId}`, { method: "PATCH", body: JSON.stringify({ is_primary: true }) }, token); await load(); }
    catch (requestError) { setError(requestError instanceof Error ? requestError.message : t("common.error")); }
    finally { setBusy(false); }
  }

  async function remove(sourceId: number) {
    if (!confirm(t("water.deleteConfirm"))) return;
    setBusy(true); setError("");
    try { await api(`/fields/${field.id}/water-sources/${sourceId}`, { method: "DELETE" }, token); await load(); }
    catch (requestError) { setError(requestError instanceof Error ? requestError.message : t("common.error")); }
    finally { setBusy(false); }
  }

  const availableSensors = data?.compatible_sensors.filter((sensor) => sensor.available) ?? [];
  return <div className="fixed inset-0 z-[2000] grid place-items-start overflow-y-auto bg-black/75 p-2 sm:place-items-center sm:p-6" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
    <section role="dialog" aria-modal="true" aria-labelledby="water-source-title" className="mt-auto max-h-[calc(100dvh-0.5rem)] w-full max-w-4xl overflow-y-auto rounded-t-3xl border border-[#3f4b42] bg-[#202421] text-white shadow-2xl sm:my-auto sm:max-h-[94vh] sm:rounded-3xl">
      <header className="sticky top-0 z-20 flex items-start justify-between gap-4 border-b border-[#39423b] bg-[#202421]/95 p-5 backdrop-blur sm:p-7"><div><p className="text-xs font-bold uppercase tracking-[.18em] text-[#84cd8a]">{field.name}</p><h2 id="water-source-title" className="mt-2 text-2xl font-semibold">{t("water.title")}</h2><p className="mt-2 text-sm text-[#9da69f]">{t("water.help")}</p></div><button onClick={onClose} aria-label={t("common.close")} className="grid h-10 w-10 shrink-0 place-items-center rounded-xl hover:bg-[#303631]"><X size={20}/></button></header>
      <div className="p-5 sm:p-7">
        <div className="flex flex-wrap items-center justify-between gap-3"><div><h3 className="font-semibold">{t("water.registered")}</h3><p className="mt-1 text-sm text-[#89938b]">{t("water.primaryHelp")}</p></div><button onClick={() => setAdding((value) => !value)} className="flex min-h-11 items-center gap-2 rounded-xl bg-[#3e8756] px-4 font-semibold hover:bg-[#4b9964]"><Plus size={18}/>{t("water.add")}</button></div>

        {adding && <form onSubmit={save} className="mt-5 rounded-2xl border border-[#465048] bg-[#272c28] p-5"><div className="grid gap-4 sm:grid-cols-2"><Label text={t("water.name")}><input name="name" required minLength={2} placeholder={t("water.nameExample")} className={control}/></Label><Label text={t("water.type")}><select name="source_type" value={sourceType} onChange={(event) => setSourceType(event.target.value)} className={control}>{types.map((item) => <option key={item} value={item}>{t(`water.type.${item}`)}</option>)}</select></Label>{sourceType === "tank" && <><Label text={t("water.capacity")} optional><input name="capacity_liters" type="number" min="1" step="any" placeholder="5000" className={control}/></Label><Label text={t("water.height")} optional><input name="tank_height_cm" type="number" min="1" step="any" placeholder="200" className={control}/></Label><label className="text-sm text-[#bdc5bf] sm:col-span-2">{t("water.sensor")} <span className="text-[#758078]">({t("common.optional")})</span><select name="sensor_id" className={`${control} mt-2`}><option value="">{availableSensors.length ? t("water.sensorLater") : t("water.noSensor")}</option>{availableSensors.map((sensor) => <option key={sensor.id} value={sensor.id}>{sensor.device_name} · {sensor.name} {sensor.unit ? `(${sensor.unit})` : ""}</option>)}</select><small className="mt-2 block text-[#7f8a82]">{t("water.sensorHelp")}</small></label></>}<Label text={t("common.notes")} optional wide><textarea name="notes" rows={2} className={control}/></Label><label className="flex items-center gap-3 text-sm text-[#c5ccc7] sm:col-span-2"><input name="is_primary" type="checkbox" className="h-4 w-4 accent-[#64ad70]"/>{t("water.primary")}</label></div><div className="mt-5 flex gap-3"><button disabled={busy} className="flex min-h-11 items-center gap-2 rounded-xl bg-[#438a56] px-5 font-semibold disabled:opacity-50">{busy ? <LoaderCircle className="animate-spin" size={17}/> : <Droplets size={17}/>} {t("water.save")}</button><button type="button" onClick={() => setAdding(false)} className="min-h-11 rounded-xl border border-[#4b554d] px-5">{t("common.cancel")}</button></div></form>}

        {message && <p className="mt-4 flex items-center gap-2 rounded-xl bg-[#29402d] p-3 text-sm text-[#b9dcae]"><CheckCircle2 size={17}/>{message}</p>}{error && <p role="alert" className="mt-4 rounded-xl bg-[#442a26] p-3 text-sm text-[#ebb4a8]">{error}</p>}
        {!data ? <div className="grid min-h-44 place-items-center"><LoaderCircle className="animate-spin text-[#83c982]"/></div> : data.sources.length === 0 ? <div className="mt-5 rounded-2xl border border-dashed border-[#465048] p-10 text-center text-[#8d978f]"><Waves className="mx-auto mb-3" size={30}/><p>{t("water.empty")}</p></div> : <div className="mt-5 grid gap-4 md:grid-cols-2">{data.sources.map((source) => <SourceCard key={source.id} source={source} locale={locale} t={t} busy={busy} onPrimary={() => void makePrimary(source.id)} onDelete={() => void remove(source.id)}/>)}</div>}
      </div>
    </section>
  </div>;
}

function SourceCard({ source, locale, t, busy, onPrimary, onDelete }: { source: Source; locale: string; t: (key: string, fallback?: string) => string; busy: boolean; onPrimary: () => void; onDelete: () => void }) {
  const level = source.latest_level;
  return <article className={`rounded-2xl border p-5 ${source.is_primary ? "border-[#5e8d64] bg-[#29382c]" : "border-[#3e4740] bg-[#272c28]"}`}><div className="flex items-start justify-between gap-3"><span className="flex min-w-0 items-center gap-3"><span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-[#304634] text-[#89cf8d]">{source.source_type === "tank" ? <Droplets/> : <Waves/>}</span><span className="min-w-0"><strong className="block truncate">{source.name}</strong><small className="mt-1 block capitalize text-[#8f9991]">{t(`water.type.${source.source_type}`, source.source_type)}</small></span></span>{source.is_primary && <span className="flex shrink-0 items-center gap-1 rounded-full bg-[#3c5a40] px-2.5 py-1 text-[11px] font-bold text-[#b6dfb1]"><Star size={12}/>{t("water.primaryShort")}</span>}</div>
    {source.source_type === "tank" && <div className="mt-5">{level?.remaining_percent != null ? <><div className="flex items-end justify-between gap-3"><div><span className="text-xs uppercase tracking-wider text-[#89938b]">{t("water.remaining")}</span><strong className="mt-1 block text-3xl">{level.remaining_percent.toFixed(1)}%</strong></div>{level.remaining_liters != null && <strong className="text-[#aad7a8]">{Math.round(level.remaining_liters).toLocaleString(locale)} L</strong>}</div><div className="mt-3 h-2.5 overflow-hidden rounded-full bg-[#1c211d]"><div className={`h-full rounded-full ${level.remaining_percent < 15 ? "bg-[#d56f5e]" : level.remaining_percent < 35 ? "bg-[#d5a65e]" : "bg-[#64b471]"}`} style={{ width: `${level.remaining_percent}%` }}/></div><p className="mt-3 flex items-center gap-2 text-xs text-[#89938b]"><Radio size={13}/>{level.simulated ? t("water.simulated") : t("water.live")} · {new Date(level.recorded_at).toLocaleString(locale)}</p></> : <div className="rounded-xl border border-dashed border-[#4a554c] p-4 text-sm text-[#99a29b]"><Gauge className="mb-2" size={19}/>{level?.limitation || (source.sensor_id ? t("water.noReading") : t("water.noLinkedSensor"))}</div>}{source.capacity_liters && <p className="mt-3 text-xs text-[#7f8981]">{t("water.capacity")}: {source.capacity_liters.toLocaleString(locale)} L{source.tank_height_cm ? ` · ${source.tank_height_cm} cm` : ""}</p>}</div>}
    {source.source_type !== "tank" && <p className="mt-4 rounded-xl bg-[#222723] p-3 text-sm text-[#a7b0a9]">{t("water.nonTankNote")}</p>}{source.notes && <p className="mt-3 text-sm text-[#929c94]">{source.notes}</p>}
    <div className="mt-4 flex items-center gap-2 border-t border-[#3a433c] pt-4">{!source.is_primary && <button disabled={busy} onClick={onPrimary} className="flex min-h-10 items-center gap-2 rounded-lg border border-[#4c5d50] px-3 text-sm hover:bg-[#344037]"><Star size={15}/>{t("water.makePrimary")}</button>}<button disabled={busy} onClick={onDelete} aria-label={t("common.delete")} className="ml-auto grid h-10 w-10 place-items-center rounded-lg text-[#dd8d82] hover:bg-[#472b28]"><Trash2 size={17}/></button></div>
  </article>;
}

const control = "w-full rounded-xl border border-[#4a534c] bg-[#1b1e1c] p-3 text-white outline-none focus:border-[#73b979]";
function Label({ text, optional = false, wide = false, children }: { text: string; optional?: boolean; wide?: boolean; children: React.ReactNode }) { const { t } = useI18n(); return <label className={`text-sm text-[#bdc5bf] ${wide ? "sm:col-span-2" : ""}`}>{text} {optional && <span className="text-[#758078]">({t("common.optional")})</span>}<span className="mt-2 block">{children}</span></label>; }
